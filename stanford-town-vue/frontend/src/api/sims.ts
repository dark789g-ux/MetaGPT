import { apiClient } from './client'

// Real return types come from openapi-typescript in M3; using `any` for now.

export interface CreateSimBody {
  sim_code: string
  start_hms?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any
}

export interface StepsRange {
  from?: number
  to?: number
}

export interface PersonaMemoryOpts {
  kind?: string
  limit?: number
  offset?: number
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function listSims(): Promise<any> {
  const res = await apiClient.get('/sims')
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getSim(id: number): Promise<any> {
  const res = await apiClient.get(`/sims/${id}`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function createSim(body: CreateSimBody): Promise<any> {
  const res = await apiClient.post('/sims', body)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function pauseSim(id: number): Promise<any> {
  const res = await apiClient.post(`/sims/${id}/pause`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function resumeSim(id: number): Promise<any> {
  const res = await apiClient.post(`/sims/${id}/resume`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function stopSim(id: number): Promise<any> {
  const res = await apiClient.post(`/sims/${id}/stop`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function deleteSim(id: number): Promise<any> {
  const res = await apiClient.delete(`/sims/${id}`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getSteps(id: number, from?: number, to?: number): Promise<any> {
  const params: StepsRange = {}
  if (from != null) params.from = from
  if (to != null) params.to = to
  const res = await apiClient.get(`/sims/${id}/steps`, { params })
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getStep(id: number, step: number): Promise<any> {
  const res = await apiClient.get(`/sims/${id}/steps/${step}`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getSimPersonas(id: number): Promise<any> {
  const res = await apiClient.get(`/sims/${id}/personas`)
  return res.data
}

export async function getPersonaState(
  id: number,
  name: string,
  step: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<any> {
  const res = await apiClient.get(`/sims/${id}/personas/${encodeURIComponent(name)}/state`, {
    params: { step },
  })
  return res.data
}

export async function getPersonaMemory(
  id: number,
  name: string,
  opts: PersonaMemoryOpts = {},
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<any> {
  const res = await apiClient.get(`/sims/${id}/personas/${encodeURIComponent(name)}/memory`, {
    params: opts,
  })
  return res.data
}
