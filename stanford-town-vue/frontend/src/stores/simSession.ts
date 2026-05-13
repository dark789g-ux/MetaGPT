import { defineStore } from 'pinia'
import type { StepMovement } from '@/types/sim'

interface SimSessionState {
  simId: number | null
  currentStep: number
  speed: number
  isPlaying: boolean
  stepBuffer: StepMovement[]
}

export const useSimSessionStore = defineStore('simSession', {
  state: (): SimSessionState => ({
    simId: null,
    currentStep: 0,
    speed: 1,
    isPlaying: false,
    stepBuffer: [],
  }),
  getters: {
    bufferSize: (state) => state.stepBuffer.length,
  },
  actions: {
    setSim(_id: number) {
      console.warn('[simSession.setSim] stub — implemented in M4/M5')
    },
    play() {
      console.warn('[simSession.play] stub — implemented in M4/M5')
    },
    pause() {
      console.warn('[simSession.pause] stub — implemented in M4/M5')
    },
    seek(_step: number) {
      console.warn('[simSession.seek] stub — implemented in M4/M5')
    },
    pushSteps(_steps: StepMovement[]) {
      console.warn('[simSession.pushSteps] stub — implemented in M4/M5')
    },
  },
})
