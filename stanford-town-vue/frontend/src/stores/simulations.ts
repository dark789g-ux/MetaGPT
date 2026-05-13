import { defineStore } from 'pinia'
import type { Simulation } from '@/types/sim'

interface SimulationsState {
  list: Simulation[]
  loading: boolean
  error: string | null
}

export const useSimulationsStore = defineStore('simulations', {
  state: (): SimulationsState => ({
    list: [],
    loading: false,
    error: null,
  }),
  getters: {
    count: (state) => state.list.length,
    byId: (state) => (id: number) => state.list.find((s) => s.id === id),
  },
  actions: {
    async fetchAll() {
      console.warn('[simulations.fetchAll] stub — implemented in M5')
    },
    async create(_body: Record<string, unknown>) {
      console.warn('[simulations.create] stub — implemented in M5')
      return null
    },
    async remove(_id: number) {
      console.warn('[simulations.remove] stub — implemented in M5')
    },
  },
})
