import { defineStore } from 'pinia'

interface LlmProfile {
  id: number
  name: string
  provider: string
  model: string
  [k: string]: unknown
}

interface LlmProfilesState {
  list: LlmProfile[]
  loading: boolean
  error: string | null
}

export const useLlmProfilesStore = defineStore('llmProfiles', {
  state: (): LlmProfilesState => ({
    list: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetchAll() {
      console.warn('[llmProfiles.fetchAll] stub — implemented in M5')
    },
    async create(_body: Partial<LlmProfile>) {
      console.warn('[llmProfiles.create] stub — implemented in M5')
      return null
    },
    async update(_id: number, _body: Partial<LlmProfile>) {
      console.warn('[llmProfiles.update] stub — implemented in M5')
    },
    async remove(_id: number) {
      console.warn('[llmProfiles.remove] stub — implemented in M5')
    },
    async test(_id: number) {
      console.warn('[llmProfiles.test] stub — implemented in M5')
      return { ok: false }
    },
  },
})
