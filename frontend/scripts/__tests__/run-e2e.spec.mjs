// @vitest-environment node
import path from 'node:path'
import process from 'node:process'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import {
  runPlaywright,
  shutdownOwnedProcess,
  signalOwnedProcess,
  spawnOwned,
  terminateOwnedProcess,
  waitForExit,
  windowsTaskkillArgs
} from '../run-e2e-processes.mjs'

const fixturesDir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures')

function waitForPid(child) {
  return new Promise((resolve, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error('等待后代PID超时')), 5_000)
    child.stdout.on('data', (chunk) => {
      output += chunk.toString('utf8')
      const firstLine = output.split(/\r?\n/, 1)[0]
      if (/^\d+$/.test(firstLine)) {
        clearTimeout(timer)
        resolve(Number(firstLine))
      }
    })
  })
}

function isPidAlive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    if (error.code === 'ESRCH') return false
    throw error
  }
}

describe('run-e2e process ownership', () => {
  it('不存在的可执行文件在spawnOwned返回前以ENOENT拒绝', async () => {
    await expect(
      spawnOwned('__codex_missing_e2e_executable__', [], { stdio: 'ignore' })
    ).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('回收runner明确创建的父进程树并确认父进程和后代都退出', async () => {
    const child = await spawnOwned(
      process.execPath,
      [path.join(fixturesDir, 'parent-tree.mjs')],
      { stdio: ['ignore', 'pipe', 'ignore'] }
    )
    const descendantPid = await waitForPid(child)
    const runTaskkill = vi.fn(async (rootPid) => {
      expect(rootPid).toBe(child.pid)
      process.kill(descendantPid)
      child.kill()
      await Promise.all([waitForExit(child, 2_000)])
      return { code: 0, stderr: '' }
    })

    try {
      await terminateOwnedProcess(child, 2_000, { platform: 'win32', runTaskkill })
      expect(await waitForExit(child, 500)).toBe(true)
      expect(isPidAlive(descendantPid)).toBe(false)
      expect(runTaskkill).toHaveBeenCalledOnce()
    } finally {
      if (isPidAlive(descendantPid)) process.kill(descendantPid)
    }
  }, 15_000)

  it('Windows默认taskkill参数只包含精确owned root PID和树终止开关', () => {
    expect(windowsTaskkillArgs(4321)).toEqual(['/PID', '4321', '/T', '/F'])
  })

  it('协作式shutdown成功时root以0退出且不调用taskkill fallback', async () => {
    const child = await spawnOwned(
      process.execPath,
      [path.join(fixturesDir, 'cooperative-child.mjs'), 'cooperate'],
      { stdio: ['pipe', 'ignore', 'ignore'] }
    )
    const terminateFallback = vi.fn()

    await shutdownOwnedProcess(child, 2_000, { terminateFallback })

    expect(child.exitCode).toBe(0)
    expect(terminateFallback).not.toHaveBeenCalled()
  })

  it('协作式shutdown超时后进入精确tree fallback', async () => {
    const child = await spawnOwned(
      process.execPath,
      [path.join(fixturesDir, 'cooperative-child.mjs'), 'ignore'],
      { stdio: ['pipe', 'ignore', 'ignore'] }
    )
    const terminateFallback = vi.fn(async (ownedChild) => {
      ownedChild.kill()
      await waitForExit(ownedChild, 1_000)
    })

    await shutdownOwnedProcess(child, 100, { terminateFallback })

    expect(terminateFallback).toHaveBeenCalledOnce()
    expect(terminateFallback).toHaveBeenCalledWith(child)
  })

  it('协作式shutdown超时且tree fallback失败时传播cleanup错误', async () => {
    const child = await spawnOwned(
      process.execPath,
      [path.join(fixturesDir, 'cooperative-child.mjs'), 'ignore'],
      { stdio: ['pipe', 'ignore', 'ignore'] }
    )
    const terminateFallback = vi.fn().mockRejectedValue(new Error('taskkill denied'))

    try {
      await expect(
        shutdownOwnedProcess(child, 100, { terminateFallback })
      ).rejects.toThrow(/taskkill denied/)
    } finally {
      child.kill()
      await waitForExit(child, 1_000)
    }
  })

  it('Windows信号路径通过wrapper控制通道转发SIGTERM并有界退出', async () => {
    const child = await spawnOwned(
      process.execPath,
      [path.join(fixturesDir, 'cooperative-child.mjs'), 'cooperate'],
      { stdio: ['pipe', 'ignore', 'ignore'] }
    )
    const terminateFallback = vi.fn()

    await signalOwnedProcess(child, 'SIGTERM', 2_000, {
      platform: 'win32',
      terminateFallback
    })

    expect(child.exitCode).toBe(143)
    expect(terminateFallback).not.toHaveBeenCalled()
  })

  it('taskkill失败时即使精确child kill成功也必须报告cleanup失败', async () => {
    const child = await spawnOwned(
      process.execPath,
      ['-e', 'setInterval(() => {}, 1000)'],
      { stdio: 'ignore' }
    )
    const runTaskkill = vi.fn().mockResolvedValue({ code: 5, stderr: 'Access is denied.' })

    await expect(
      terminateOwnedProcess(child, 2_000, { platform: 'win32', runTaskkill })
    ).rejects.toThrow(/taskkill.*失败|cleanup.*失败/i)
    expect(runTaskkill).toHaveBeenCalledWith(child.pid, 2_000)
    expect(await waitForExit(child, 1_000)).toBe(true)
  }, 10_000)

  it('拒绝终止未由runner登记的PID', async () => {
    const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {
      stdio: 'ignore',
      windowsHide: true
    })
    await new Promise((resolve, reject) => {
      child.once('spawn', resolve)
      child.once('error', reject)
    })
    try {
      await expect(terminateOwnedProcess(child)).rejects.toThrow(/非runner自有PID/)
      expect(isPidAlive(child.pid)).toBe(true)
    } finally {
      child.kill()
      await waitForExit(child, 2_000)
    }
  })

  it('Playwright非零退出码原样传播', async () => {
    const exitCode = await runPlaywright([], {
      cliPath: path.join(fixturesDir, 'exit-seven.mjs'),
      cwd: fixturesDir
    })

    expect(exitCode).toBe(7)
  })
})
