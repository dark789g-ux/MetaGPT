// Skeleton WebSocket client for live simulation events.
// Real event payload handling is implemented by consumers in M4/M5.

export type SimWsEvent = {
  type: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any
}

export type SimWsEventHandler = (event: SimWsEvent) => void

const HEARTBEAT_INTERVAL_MS = 30_000
const MAX_RECONNECT_ATTEMPTS = 5
const BASE_BACKOFF_MS = 500

export class SimWsClient {
  private ws: WebSocket | null = null
  private simId: number | null = null
  private sinceStep = 0
  private handler: SimWsEventHandler | null = null
  private reconnectAttempts = 0
  private heartbeatTimer: number | null = null
  private reconnectTimer: number | null = null
  private manualDisconnect = false

  connect(simId: number, sinceStep: number): void {
    this.simId = simId
    this.sinceStep = sinceStep
    this.manualDisconnect = false
    this.reconnectAttempts = 0
    this.open()
  }

  onEvent(handler: SimWsEventHandler): void {
    this.handler = handler
  }

  disconnect(): void {
    this.manualDisconnect = true
    this.clearTimers()
    if (this.ws) {
      try {
        this.ws.close()
      } catch {
        /* ignore */
      }
      this.ws = null
    }
  }

  sendPing(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: 'ping', t: Date.now() }))
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn('[SimWsClient] ping failed', err)
      }
    }
  }

  private open(): void {
    if (this.simId == null) return
    const url = `ws://${location.host}/ws/sim/${this.simId}?since=${this.sinceStep}`
    // eslint-disable-next-line no-console
    console.info('[SimWsClient] connecting', url)
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.reconnectAttempts = 0
      this.startHeartbeat()
    }

    ws.onmessage = (msg) => {
      if (!this.handler) return
      try {
        const data = JSON.parse(msg.data as string) as SimWsEvent
        this.handler(data)
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn('[SimWsClient] bad message', err)
      }
    }

    ws.onclose = () => {
      this.stopHeartbeat()
      this.ws = null
      if (!this.manualDisconnect) {
        this.scheduleReconnect()
      }
    }

    ws.onerror = (err) => {
      // eslint-disable-next-line no-console
      console.warn('[SimWsClient] error', err)
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      // eslint-disable-next-line no-console
      console.error('[SimWsClient] max reconnect attempts reached')
      return
    }
    const delay = BASE_BACKOFF_MS * 2 ** this.reconnectAttempts
    this.reconnectAttempts += 1
    this.reconnectTimer = window.setTimeout(() => this.open(), delay)
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => this.sendPing(), HEARTBEAT_INTERVAL_MS)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer != null) {
      window.clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private clearTimers(): void {
    this.stopHeartbeat()
    if (this.reconnectTimer != null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }
}
