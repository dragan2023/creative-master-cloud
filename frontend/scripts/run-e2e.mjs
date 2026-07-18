/**
 * Playwright E2E runner：显式拥有、探活并回收本次启动的前后端进程。
 *
 * 安全边界：
 * - 3001/8002被占用时失败，不复用、不终止既有服务。
 * - 只终止spawnOwned登记的PID/进程组，并轮询确认实际退出。
 * - 启动、探活、信号清理均有硬超时；Playwright退出码原样传播。
 */
import net from 'node:net'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import {
  installSignalCleanup,
  runPlaywright,
  shutdownOwnedProcess,
  signalOwnedProcess,
  spawnOwned,
} from './run-e2e-processes.mjs'

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = path.resolve(frontendDir, '..', 'backend')
const STARTUP_TIMEOUT_MS = 30_000
const REQUEST_TIMEOUT_MS = 2_000
const POLL_INTERVAL_MS = 250

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
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
    throw new Error(`E2E runner拒绝复用或终止已有服务；请先释放端口: ${occupied.join(', ')}`)
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
      socket.write(`GET ${parsed.pathname}${parsed.search} HTTP/1.1\r\nHost: ${parsed.host}\r\nConnection: close\r\n\r\n`)
    })
    socket.on('data', (chunk) => {
      response += chunk.toString('utf8')
      if (response.includes('\r\n')) finish(/^HTTP\/1\.[01] 2\d\d/.test(response))
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
      throw new Error(`${label}在健康检查前退出，exit=${child.exitCode}, signal=${child.signalCode}`)
    }
    if (await requestOk(url)) return
    await delay(POLL_INTERVAL_MS)
  }
  throw new Error(`${label}健康检查超时${STARTUP_TIMEOUT_MS}ms: ${url}`)
}

async function main() {
  const pythonPath = process.platform === 'win32'
    ? path.join(backendDir, 'venv', 'Scripts', 'python.exe')
    : path.join(backendDir, 'venv', 'bin', 'python')
  const backendWrapperPath = path.join(backendDir, 'scripts', 'run_e2e_server.py')
  const viteWrapperPath = path.join(frontendDir, 'scripts', 'run-e2e-vite.mjs')
  const ownedChildren = []
  let cleanupPromise = null
  const cleanup = (signal = null) => {
    if (!cleanupPromise) {
      cleanupPromise = (async () => {
        const errors = []
        for (const child of [...ownedChildren].reverse()) {
          try {
            if (signal) {
              await signalOwnedProcess(child, signal)
            } else {
              await shutdownOwnedProcess(child)
            }
          } catch (error) {
            errors.push(error)
          }
        }
        if (errors.length) {
          throw new AggregateError(
            errors,
            `E2E自有进程清理失败: ${errors.map((error) => error?.message || error).join(' | ')}`
          )
        }
      })()
    }
    return cleanupPromise
  }
  const removeSignalHandlers = installSignalCleanup(cleanup)

  try {
    await assertOwnedPortsAreFree()
    const backend = await spawnOwned(
      pythonPath,
      [backendWrapperPath],
      {
        cwd: backendDir,
        env: { ...process.env, QA_TEST_HOOKS: '1', RUNTIME_ENV: 'test' },
        stdio: ['pipe', 'pipe', 'pipe']
      }
    )
    ownedChildren.push(backend)

    const vite = await spawnOwned(
      process.execPath,
      [viteWrapperPath],
      {
        cwd: frontendDir,
        env: { ...process.env, BROWSER: 'none', E2E_VITE_PORT: '3001' },
        stdio: ['pipe', 'pipe', 'pipe']
      }
    )
    ownedChildren.push(vite)

    await Promise.all([
      waitForHttp('http://127.0.0.1:8002/api/v1/health', backend, 'FastAPI'),
      waitForHttp('http://127.0.0.1:3001/', vite, 'Vite')
    ])

    return await runPlaywright(process.argv.slice(2), { ownedChildren })
  } finally {
    removeSignalHandlers()
    await cleanup()
  }
}

main()
  .then((exitCode) => process.exit(exitCode))
  .catch((error) => {
    console.error('[E2E runner]', error?.message || error)
    process.exit(1)
  })
