import process from 'node:process'
import readline from 'node:readline'
import { createServer } from 'vite'

const port = Number(process.env.E2E_VITE_PORT || 3001)

async function main() {
  const server = await createServer({
    server: { host: '127.0.0.1', port, strictPort: true }
  })
  await server.listen()

  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
  let settled = false
  const command = await new Promise((resolve) => {
    const finish = (value) => {
      if (settled) return
      settled = true
      resolve(value)
    }
    input.on('line', (line) => {
      const type = line.trim()
      const exitCode = type === 'signal:SIGINT' ? 130 : type === 'signal:SIGTERM' ? 143 : 0
      finish({ type, exitCode })
    })
    input.on('close', () => finish({ type: 'stdin_closed', exitCode: 1 }))
    process.once('SIGINT', () => finish({ type: 'signal', exitCode: 130 }))
    process.once('SIGTERM', () => finish({ type: 'signal', exitCode: 143 }))
  })

  input.close()
  await server.close()
  if (!['shutdown', 'signal', 'signal:SIGINT', 'signal:SIGTERM'].includes(command.type)) {
    throw new Error(`Vite E2E wrapper收到无效关闭命令: ${command.type}`)
  }
  return command.exitCode
}

main()
  .then((exitCode) => { process.exitCode = exitCode })
  .catch((error) => {
    console.error('[E2E Vite wrapper]', error?.message || error)
    process.exitCode = 1
  })
