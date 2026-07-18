// @vitest-environment node
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  runPlaywright,
  spawnOwned,
  terminateOwnedProcess,
  waitForExit
} from '../run-e2e-processes.mjs'

const fixturesDir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures')

describe('run-e2e process ownership', () => {
  it('不存在的可执行文件在spawnOwned返回前以ENOENT拒绝', async () => {
    await expect(
      spawnOwned('__codex_missing_e2e_executable__', [], { stdio: 'ignore' })
    ).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('只回收runner明确创建的测试子进程并确认退出', async () => {
    const child = await spawnOwned(
      process.execPath,
      ['-e', 'setInterval(() => {}, 1000)'],
      { stdio: 'ignore' }
    )

    await terminateOwnedProcess(child)

    expect(await waitForExit(child, 500)).toBe(true)
  }, 15_000)

  it('Playwright非零退出码原样传播', async () => {
    const exitCode = await runPlaywright([], {
      cliPath: path.join(fixturesDir, 'exit-seven.mjs'),
      cwd: fixturesDir
    })

    expect(exitCode).toBe(7)
  })
})
