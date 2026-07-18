import readline from 'node:readline'

const mode = process.argv[2] || 'cooperate'
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
lines.on('line', (line) => {
  if (mode === 'cooperate' && line.trim() === 'shutdown') process.exit(0)
  if (mode === 'cooperate' && line.trim() === 'signal:SIGTERM') process.exit(143)
})
setInterval(() => {}, 1000)
