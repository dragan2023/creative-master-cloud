/**
 * Playwright E2E runner：显式拥有、探活并回收本次启动的前后端进程。
 *
 * 安全边界：
 * - 启动前若 3001/8002 已被占用则直接失败，不复用也不终止既有服务。
 * - Windows 仅 taskkill 本 runner spawn 返回的明确 PID；POSIX 仅终止自有进程组。
 * - 所有探活、退出等待均有硬超时，Playwright 退出码原样传播。
 */
import { spawn } from 'node:child_process'
import net from 'node:net'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = path.resolve(frontendDir, '..', 'backend')
const STARTUP_TIMEOUT_MS = 30_000
const REQUEST_TIMEOUT_MS = 2_000
const STOP_TIMEOUT_MS = 5_000
const POLL_INTERVAL_MS = 250

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function waitForExit(child, timeoutMs) {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve(true)
  }
  return new Promise((resolve) => {
    let settled = false
    const finish = (exited) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      child.off('exit', onExit)
      resolve(exited)
    }
    const onExit = () => finish(true)
    const timer = setTimeout(() => finish(false), timeoutMs)
    child.once('exit', onExit)
  })
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port })
    const finish = (open) => {
      socket.removeAllListeners()
      socket.destroy()
      resolve(open)
    }
    socket.setTimeout(750)
    socket.once('connect', () => finish(true))
    socket.once('timeout', () => finish(false))
    socket.once('error', () => finish(false))
  })
}

async function assertOwnedPortsAreFree() {
  const occupied = []
  for (const port of [8002, 3001]) {
    if (await isPortOpen(port)) occupied.push(port)
  }
  if (occupied.length) {
    throw new Error(
      `E2E runner 拒绝复用或终止已有服务；请先释放端口: ${occupied.join(', ')}`
    )
  }
}

function requestOk(url) {
  return new Promise((resolve) => {
    const parsed = new URL(url)
    const socket = net.createConnection({ host: parsed.hostname, port: Number(parsed.port) })
    let response = ''
    let settled = false
    const finish = (ok) => {
      if (settled) return
      settled = true
      socket.destroy()
      resolve(ok)
    }
    socket.setTimeout(REQUEST_TIMEOUT_MS)
    socket.once('connect', () => {
      socket.write(
        `GET ${parsed.pathname}${parsed.search} HTTP/1.1\r\nHost: ${parsed.host}\r\nConnection: close\r\n\r\n`
      )
    })
    socket.on('data', (chunk) => {
      response += chunk.toString('utf8')
      if (response.includes('\r\n')) {
        finish(/^HTTP\/1\.[01] 2\d\d/.test(response))
      }
    })
    socket.once('timeout', () => finish(false))
    socket.once('error', () => finish(false))
    socket.once('end', () => finish(/^HTTP\/1\.[01] 2\d\d/.test(response)))
  })
}

async function waitForHttp(url, child, label) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`${label} 在健康检查前退出，exit=${child.exitCode}, signal=${child.signalCode}`)
    }
    if (await requestOk(url)) return
    await delay(POLL_INTERVAL_MS)
  }
  throw new Error(`${label} 健康检查超时 ${STARTUP_TIMEOUT_MS}ms: ${url}`)
}

function spawnOwned(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    shell: false,
    windowsHide: true,
    detached: process.platform !== 'win32'
  })
  child.stdout?.pipe(process.stdout)
  child.stderr?.pipe(process.stderr)
  return child
}

function releaseChildHandles(child) {
  child?.stdout?.destroy()
  child?.stderr?.destroy()
  child?.stdin?.destroy()
  child?.removeAllListeners()
  child?.unref()
}

async function terminateOwnedProcess(child) {
  if (!child?.pid || !Number.isInteger(child.pid) || child.pid <= 0) return
  if (child.exitCode !== null || child.signalCode !== null) return

  if (process.platform === 'win32') {
    const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
      shell: false,
      windowsHide: true,
      stdio: 'ignore'
    })
    const killerExited = await waitForExit(killer, STOP_TIMEOUT_MS)
    if (!killerExited) killer.kill()
    killer.unref()
    await waitForExit(child, STOP_TIMEOUT_MS)
    releaseChildHandles(child)
    return
  }

  try {
    process.kill(-child.pid, 'SIGTERM')
  } catch (error) {
    if (error.code !== 'ESRCH') throw error
  }
  if (await waitForExit(child, STOP_TIMEOUT_MS)) {
    releaseChildHandles(child)
    return
  }
  try {
    process.kill(-child.pid, 'SIGKILL')
  } catch (error) {
    if (error.code !== 'ESRCH') throw error
  }
  await waitForExit(child, STOP_TIMEOUT_MS)
  releaseChildHandles(child)
}

function runPlaywright(args) {
  const cliPath = path.join(frontendDir, 'node_modules', '@playwright', 'test', 'cli.js')
  const child = spawn(process.execPath, [cliPath, 'test', ...args], {
    cwd: frontendDir,
    env: process.env,
    shell: false,
    windowsHide: true,
    stdio: 'inherit'
  })
  return new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code, signal) => {
      resolve(code ?? (signal ? 1 : 0))
    })
  })
}

async function main() {
  await assertOwnedPortsAreFree()

  const pythonPath = process.platform === 'win32'
    ? path.join(backendDir, 'venv', 'Scripts', 'python.exe')
    : path.join(backendDir, 'venv', 'bin', 'python')
  const vitePath = path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js')
  const ownedChildren = []
  let playwrightExitCode = 1

  try {
    const backend = spawnOwned(
      pythonPath,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8002'],
      {
        cwd: backendDir,
        env: { ...process.env, QA_TEST_HOOKS: '1' },
        stdio: ['ignore', 'pipe', 'pipe']
      }
    )
    ownedChildren.push(backend)

    const vite = spawnOwned(
      process.execPath,
      [vitePath, '--host', '127.0.0.1', '--port', '3001', '--strictPort'],
      {
        cwd: frontendDir,
        env: { ...process.env, BROWSER: 'none' },
        stdio: ['ignore', 'pipe', 'pipe']
      }
    )
    ownedChildren.push(vite)

    await Promise.all([
      waitForHttp('http://127.0.0.1:8002/api/v1/health', backend, 'FastAPI'),
      waitForHttp('http://127.0.0.1:3001/', vite, 'Vite')
    ])

    playwrightExitCode = await runPlaywright(process.argv.slice(2))
  } finally {
    for (const child of ownedChildren.reverse()) {
      await terminateOwnedProcess(child)
    }
  }

  return playwrightExitCode
}

main()
  .then((exitCode) => process.exit(exitCode))
  .catch((error) => {
    console.error('[E2E runner]', error?.message || error)
    process.exit(1)
  })
