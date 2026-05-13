import { apiClient } from './client'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function importSim(sourcePath: string): Promise<any> {
  const res = await apiClient.post('/imports', { source_path: sourcePath })
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function exportSim(id: number, targetDir: string): Promise<any> {
  const res = await apiClient.post(`/sims/${id}/export`, { target_dir: targetDir })
  return res.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function listForks(): Promise<any> {
  const res = await apiClient.get('/forks')
  return res.data
}
