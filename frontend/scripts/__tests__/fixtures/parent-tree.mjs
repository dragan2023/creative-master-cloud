import { spawn } from 'node:child_process'
import process from 'node:process'

const descendant = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {
  stdio: 'ignore',
  windowsHide: true
})

process.stdout.write(`${descendant.pid}\n`)
setInterval(() => {}, 1000)
