import { spawn } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const ownedProcesses = new WeakSet()
const DEFAULT_STOP_TIMEOUT_MS = 5_000
const EXIT_POLL_INTERVAL_MS = 50

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function hasExited(child) {
  return !child || child.exitCode !== null || child.signalCode !== null
}

/** 以条件轮询确认进程已经退出，不把“已发送终止信号”误当作退出成功。 */
export async function waitForExit(child, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (!hasExited(child) && Date.now() < deadline) {
    await delay(Math.min(EXIT_POLL_INTERVAL_MS, Math.max(1, deadline - Date.now())))
  }
  return hasExited(child)
}

/**
 * 启动runner自有进程。只有收到spawn事件后才返回；ENOENT等error会先拒绝，
 * 因此调用方的try/finally始终能接管此前已经启动的其他子进程。
 */
export function spawnOwned(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    let child
    try {
      child = spawn(command, args, {
        ...options,
        shell: false,
        windowsHide: true,
        detached: process.platform !== 'win32'
      })
    } catch (error) {
      reject(error)
      return
    }

    const onError = (error) => {
      child.off('spawn', onSpawn)
      reject(error)
    }
    const onSpawn = () => {
      child.off('error', onError)
      ownedProcesses.add(child)
      child.stdout?.pipe(process.stdout)
      child.stderr?.pipe(process.stderr)
      resolve(child)
    }
    child.once('error', onError)
    child.once('spawn', onSpawn)
  })
}

function releaseChildHandles(child) {
  child?.stdout?.destroy()
  child?.stderr?.destroy()
  child?.stdin?.destroy()
  child?.removeAllListeners()
  child?.unref()
}

function waitForCommandExit(child, timeoutMs) {
  return new Promise((resolve, reject) => {
    let stderr = ''
    let settled = false
    const finish = (callback, value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      child.off('error', onError)
      child.off('exit', onExit)
      callback(value)
    }
    const onError = (error) => finish(reject, error)
    const onExit = (code, signal) => finish(resolve, {
      code: code ?? (signal ? 1 : 0),
      stderr: stderr.trim()
    })
    const timer = setTimeout(() => {
      try { child.kill() } catch {}
      finish(reject, new Error(`终止命令在${timeoutMs}ms内未退出`))
    }, timeoutMs)
    child.once('error', onError)
    child.once('exit', onExit)
    child.stderr?.on('data', (chunk) => { stderr += chunk.toString('utf8') })
  })
}

/** 仅终止由spawnOwned登记的PID/进程组，并确认目标确实退出。 */
export async function terminateOwnedProcess(child, timeoutMs = DEFAULT_STOP_TIMEOUT_MS) {
  if (!child?.pid || !Number.isInteger(child.pid) || child.pid <= 0) return
  if (!ownedProcesses.has(child)) {
    throw new Error(`拒绝终止非runner自有PID: ${child.pid}`)
  }
  if (hasExited(child)) {
    releaseChildHandles(child)
    return
  }

  if (process.platform === 'win32') {
    // 先请求精确自有子进程退出；受限Windows Job环境可能拒绝taskkill，
    // 直接ChildProcess句柄仍可安全终止且不会触及任何非自有PID。
    try {
      child.kill()
    } catch (error) {
      if (error.code !== 'ESRCH') throw error
    }
    if (await waitForExit(child, Math.min(1_000, timeoutMs))) {
      releaseChildHandles(child)
      return
    }

    const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
      shell: false,
      windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe']
    })
    const taskkillResult = await waitForCommandExit(killer, timeoutMs)
    const exited = await waitForExit(child, timeoutMs)
    if (taskkillResult.code !== 0 && !exited) {
      throw new Error(
        `taskkill终止自有PID ${child.pid}失败，exit=${taskkillResult.code}` +
        (taskkillResult.stderr ? `, stderr=${taskkillResult.stderr}` : '')
      )
    }
    if (!exited) {
      throw new Error(`taskkill完成后自有PID ${child.pid}仍未退出`)
    }
    releaseChildHandles(child)
    return
  }

  try {
    process.kill(-child.pid, 'SIGTERM')
  } catch (error) {
    if (error.code !== 'ESRCH') throw error
  }
  if (await waitForExit(child, timeoutMs)) {
    releaseChildHandles(child)
    return
  }
  try {
    process.kill(-child.pid, 'SIGKILL')
  } catch (error) {
    if (error.code !== 'ESRCH') throw error
  }
  if (!(await waitForExit(child, timeoutMs))) {
    throw new Error(`SIGKILL后自有进程组 ${child.pid}仍未退出`)
  }
  releaseChildHandles(child)
}

export async function runPlaywright(args, options = {}) {
  const cliPath = options.cliPath || path.join(frontendDir, 'node_modules', '@playwright', 'test', 'cli.js')
  const child = await spawnOwned(process.execPath, [cliPath, ...(options.cliPath ? [] : ['test']), ...args], {
    cwd: options.cwd || frontendDir,
    env: options.env || process.env,
    stdio: options.stdio || 'inherit'
  })
  options.ownedChildren?.push(child)
  return new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code, signal) => resolve(code ?? (signal ? 1 : 0)))
  })
}

/** SIGINT/SIGTERM仅注册一次；清理有界，退出码保留shell惯例。 */
export function installSignalCleanup(cleanup, processRef = process) {
  let handlingSignal = false
  const handlers = new Map()
  for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
    const handler = async () => {
      if (handlingSignal) return
      handlingSignal = true
      try {
        await cleanup()
      } catch (error) {
        console.error('[E2E runner] 信号清理失败:', error?.message || error)
      } finally {
        processRef.exit(exitCode)
      }
    }
    handlers.set(signal, handler)
    processRef.once(signal, handler)
  }
  return () => {
    for (const [signal, handler] of handlers) processRef.off(signal, handler)
  }
}
