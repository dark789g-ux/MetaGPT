import { apiClient } from './client'
import { getEffectiveConfig as _getEffectiveConfig } from './config'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getMetaPersonas(): Promise<any> {
  const res = await apiClient.get('/meta/personas')
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getMetaMaps(): Promise<any> {
  const res = await apiClient.get('/meta/maps')
  return res.data
}

export const getEffectiveConfig = _getEffectiveConfig
