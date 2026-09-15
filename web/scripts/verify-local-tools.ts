import { existsSync } from 'node:fs'
import path from 'node:path'

type BunRuntime = typeof globalThis & {
  Bun: {
    sleep: (ms: number) => Promise<void>
    spawn: (options: {
      cmd: string[]
      cwd: string
      env: Record<string, string | undefined>
      stdout: 'ignore'
      stderr: 'pipe'
    }) => { kill: () => void; exited: Promise<number>; exitCode: number | null; stderr: ReadableStream<Uint8Array> | null }
  }
}

const bunRuntime = globalThis as BunRuntime

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

async function waitForHealthy(baseUrl: string) {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${baseUrl}/tools/health`)).ok) return
    } catch {
      // The backend may still be starting.
    }
    await bunRuntime.Bun.sleep(250)
  }
  throw new Error('Timed out waiting for the inline REST tools endpoint')
}

async function main() {
  const serverRoot = path.resolve(process.cwd(), '..', 'server')
  const venvPython = path.join(serverRoot, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  if (!existsSync(venvPython)) throw new Error('Missing server virtualenv. Run bun run setup:server first.')

  const port = 43160 + Math.floor(Math.random() * 20)
  const baseUrl = `http://127.0.0.1:${port}`
  const apiKey = 'test-tool-key'
  const serverProcess = bunRuntime.Bun.spawn({
    cmd: [venvPython, 'scripts/run_fake_server.py'],
    cwd: serverRoot,
    env: {
      ...process.env,
      AGORA_APP_ID: '0123456789abcdef0123456789abcdef',
      AGORA_APP_CERTIFICATE: 'fedcba9876543210fedcba9876543210',
      HTTP_TOOLS_BASE_URL: 'https://example.ngrok-free.dev',
      HTTP_TOOLS_API_KEY: apiKey,
      PORT: String(port),
    },
    stdout: 'ignore',
    stderr: 'pipe',
  })

  try {
    await waitForHealthy(baseUrl)
    const unauthorized = await fetch(`${baseUrl}/tools/orders/A-1001`)
    assert(unauthorized.status === 401, 'REST tools should reject missing API keys')

    const order = await fetch(`${baseUrl}/tools/orders/A-1001`, {
      headers: { 'X-Tool-API-Key': apiKey },
    })
    assert(order.status === 200, 'GET /tools/orders should return 200 with the API key')
    const orderBody = (await order.json()) as { status?: string }
    assert(orderBody.status === 'shipped', 'GET /tools/orders should return mock order data')

    const ticket = await fetch(`${baseUrl}/tools/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tool-API-Key': apiKey },
      body: JSON.stringify({ order_id: 'A-1001', issue: 'Package is late' }),
    })
    assert(ticket.status === 200, 'POST /tools/tickets should return 200 with the API key')
    const ticketBody = (await ticket.json()) as { status?: string }
    assert(ticketBody.status === 'created', 'POST /tools/tickets should create a ticket')
    console.log('Inline REST tools endpoint smoke check passed')
  } finally {
    serverProcess.kill()
    await serverProcess.exited
  }
}

await main()
