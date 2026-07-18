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
        // 独立进程组让root PID拥有清晰的树边界；Windows taskkill /T与
        // POSIX负进程组PID都只作用于本次spawnOwned创建的树。
        detached: true
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
      clearInterval(poller)
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
    // 某些Windows宿主不会可靠派发taskkill的exit事件，但exitCode仍会更新；
    // 条件轮询避免把已完成命令误判为超时。
    const poller = setInterval(() => {
      if (child.exitCode !== null || child.signalCode !== null) {
        onExit(child.exitCode, child.signalCode)
      }
    }, EXIT_POLL_INTERVAL_MS)
    child.once('error', onError)
    child.once('exit', onExit)
    child.stderr?.on('data', (chunk) => { stderr += chunk.toString('utf8') })
  })
}

export function windowsTaskkillArgs(pid) {
  return ['/PID', String(pid), '/T', '/F']
}

async function runWindowsTaskkill(pid, timeoutMs) {
  const killer = spawn('taskkill', windowsTaskkillArgs(pid), {
    shell: false,
    windowsHide: true,
    // taskkill在部分Windows宿主会让捕获管道保持打开，导致进程已完成但Node
    // 等不到exit；全ignore避免cleanup假超时。非零结果因此按更严格的失败处理。
    stdio: 'ignore'
  })
  return waitForCommandExit(killer, timeoutMs)
}

async function bestEffortKillExactChild(child, timeoutMs) {
  try {
    child.kill()
  } catch (error) {
    if (error.code !== 'ESRCH') return false
  }
  return waitForExit(child, timeoutMs)
}

function assertOwnedChild(child) {
  if (!child?.pid || !Number.isInteger(child.pid) || child.pid <= 0) return false
  if (!ownedProcesses.has(child)) {
    throw new Error(`拒绝终止非runner自有PID: ${child.pid}`)
  }
  return true
}

function writeControlCommand(child, command) {
  return new Promise((resolve, reject) => {
    if (!child.stdin || child.stdin.destroyed || !child.stdin.writable) {
      reject(new Error(`自有PID ${child.pid}没有可写控制通道`))
      return
    }
    child.stdin.write(`${command}\n`, (error) => error ? reject(error) : resolve())
  })
}

/**
 * 正常清理优先通过stdin与wrapper协作关闭；仅通道错误或有界等待超时才进入
 * 精确owned tree fallback。fallback失败必须继续向runner传播。
 */
export async function shutdownOwnedProcess(
  child,
  timeoutMs = DEFAULT_STOP_TIMEOUT_MS,
  dependencies = {}
) {
  if (!assertOwnedChild(child)) return
  if (hasExited(child)) {
    releaseChildHandles(child)
    return
  }

  const terminateFallback = dependencies.terminateFallback ||
    ((ownedChild) => terminateOwnedProcess(ownedChild, timeoutMs))
  try {
    await writeControlCommand(child, 'shutdown')
  } catch {
    await terminateFallback(child)
    return
  }

  if (await waitForExit(child, timeoutMs)) {
    if (child.exitCode !== 0) {
      releaseChildHandles(child)
      throw new Error(`自有wrapper PID ${child.pid}协作关闭后非零退出: ${child.exitCode}`)
    }
    releaseChildHandles(child)
    return
  }

  await terminateFallback(child)
}

/** 信号路径先转发原信号并等待；超时才回退到精确owned tree终止。 */
export async function signalOwnedProcess(
  child,
  signal,
  timeoutMs = DEFAULT_STOP_TIMEOUT_MS,
  dependencies = {}
) {
  if (!assertOwnedChild(child)) return
  if (hasExited(child)) {
    releaseChildHandles(child)
    return
  }
  const terminateFallback = dependencies.terminateFallback ||
    ((ownedChild) => terminateOwnedProcess(ownedChild, timeoutMs))
  const platform = dependencies.platform || process.platform
  try {
    if (platform === 'win32') {
      await writeControlCommand(child, `signal:${signal}`)
    } else {
      process.kill(-child.pid, signal)
    }
  } catch (error) {
    if (error.code !== 'ESRCH') {
      await terminateFallback(child)
      return
    }
  }
  if (await waitForExit(child, timeoutMs)) {
    releaseChildHandles(child)
    return
  }
  await terminateFallback(child)
}

/** 仅终止由spawnOwned登记的PID/进程组，并确认目标确实退出。 */
export async function terminateOwnedProcess(
  child,
  timeoutMs = DEFAULT_STOP_TIMEOUT_MS,
  dependencies = {}
) {
  if (!assertOwnedChild(child)) return
  if (hasExited(child)) {
    releaseChildHandles(child)
    return
  }

  const platform = dependencies.platform || process.platform
  if (platform === 'win32') {
    const runTaskkill = dependencies.runTaskkill || runWindowsTaskkill
    let taskkillResult
    try {
      // 活着的Windows自有进程必须先按精确root PID终止整个树。
      taskkillResult = await runTaskkill(child.pid, timeoutMs)
    } catch (error) {
      await bestEffortKillExactChild(child, timeoutMs)
      releaseChildHandles(child)
      throw new Error(`taskkill不可用，cleanup失败: PID ${child.pid}`, { cause: error })
    }

    const rootExited = await waitForExit(child, timeoutMs)
    if (taskkillResult.code === 0 && rootExited) {
      releaseChildHandles(child)
      return
    }
    await bestEffortKillExactChild(child, timeoutMs)
    releaseChildHandles(child)
    throw new Error(
      `taskkill终止自有PID ${child.pid}失败，exit=${taskkillResult.code}, rootExited=${rootExited}` +
      (taskkillResult.stderr ? `, stderr=${taskkillResult.stderr}` : '')
    )
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
        await cleanup(signal)
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
