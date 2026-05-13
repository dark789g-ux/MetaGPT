import { defineStore } from 'pinia'

interface LlmLogsState {
  simId: number | null
  logs: unknown[]
  loading: boolean
  cursor: number | null
}

export const useLlmLogsStore = defineStore('llmLogs', {
  state: (): LlmLogsState => ({
    simId: null,
    logs: [],
    loading: false,
    cursor: null,
  }),
  actions: {
    async fetch(_simId: number, _opts?: Record<string, unknown>) {
      console.warn('[llmLogs.fetch] stub — implemented in M6')
    },
    async loadCall(_simId: number, _callId: number) {
      console.warn('[llmLogs.loadCall] stub — implemented in M6')
      return null
    },
  },
})
