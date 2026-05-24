const BASE_URL = import.meta.env.VITE_API_URL || '/api'

export type ProgressStep =
  | 'crawling'
  | 'image_selection'
  | 'preprocessing'
  | 'dimension'
  | 'model_generation'
  | 'completed'
  | 'error'

export interface GenerationProgressEvent {
  job_id: string
  step: ProgressStep
  status: 'pending' | 'processing' | 'completed' | 'error'
  progress: number
  message?: string
  glb_url?: string
  dimensions?: {
    width: number
    height: number
    depth: number
    unit: 'cm'
  }
}

export const startGeneration = async (
  url: string,
  selectedImageIndex = 0,
): Promise<{ job_id: string }> => {
  const res = await fetch(`${BASE_URL}/process/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, selected_image_index: selectedImageIndex }),
  })
  if (!res.ok) throw new Error('generation_failed')
  return res.json()
}

export const createSSEConnection = (jobId: string): EventSource =>
  new EventSource(`${BASE_URL}/process/status/${jobId}`)
