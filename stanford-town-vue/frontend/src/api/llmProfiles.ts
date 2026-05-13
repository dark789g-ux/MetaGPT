import { apiClient } from './client'

export interface LlmProfileBody {
  name?: string
  provider?: string
  model?: string
  api_key?: string
  api_base?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function listLlmProfiles(): Promise<any> {
  const res = await apiClient.get('/llm-profiles')
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getLlmProfile(id: number): Promise<any> {
  const res = await apiClient.get(`/llm-profiles/${id}`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function createLlmProfile(body: LlmProfileBody): Promise<any> {
  const res = await apiClient.post('/llm-profiles', body)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function updateLlmProfile(id: number, body: LlmProfileBody): Promise<any> {
  const res = await apiClient.put(`/llm-profiles/${id}`, body)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function deleteLlmProfile(id: number): Promise<any> {
  const res = await apiClient.delete(`/llm-profiles/${id}`)
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function testProfile(id: number): Promise<any> {
  const res = await apiClient.post(`/llm-profiles/${id}/test`)
  return res.data
}
