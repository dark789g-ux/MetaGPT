import { defineStore } from 'pinia'

interface AppConfigState {
  effective: Record<string, unknown> | null
  personas: string[]
  maps: string[]
  loaded: boolean
}

export const useAppConfigStore = defineStore('appConfig', {
  state: (): AppConfigState => ({
    effective: null,
    personas: [],
    maps: [],
    loaded: false,
  }),
  actions: {
    async load() {
      console.warn('[appConfig.load] stub — implemented in M5')
    },
  },
})
