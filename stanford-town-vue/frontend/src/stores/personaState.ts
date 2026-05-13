import { defineStore } from 'pinia'

interface PersonaStateState {
  simId: number | null
  personaName: string | null
  step: number | null
  scratch: Record<string, unknown> | null
  memory: unknown[]
  loading: boolean
}

export const usePersonaStateStore = defineStore('personaState', {
  state: (): PersonaStateState => ({
    simId: null,
    personaName: null,
    step: null,
    scratch: null,
    memory: [],
    loading: false,
  }),
  actions: {
    async load(_simId: number, _name: string, _step: number) {
      console.warn('[personaState.load] stub — implemented in M6')
    },
    async loadMemory(_simId: number, _name: string, _opts?: Record<string, unknown>) {
      console.warn('[personaState.loadMemory] stub — implemented in M6')
    },
  },
})
