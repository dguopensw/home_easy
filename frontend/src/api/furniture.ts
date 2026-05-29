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

export interface ScrapeResponse {
  scrape_id: string
  title: string
  description: string
  price: string
  platform: string
  image_urls: string[]
  ai_recommended_image_index: number
  ranked_candidate_indices: number[]
  furniture_guess: {
    type: string
    confidence: string
  }
  dimensions_from_listing: {
    width_cm: number
    depth_cm: number
    height_cm: number
  } | null
}

export const scrapeUrl = async (url: string): Promise<ScrapeResponse> => {
  const res = await fetch(`${BASE_URL}/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error('scrape_failed')
  return res.json()
}

export const startProcess = async (
  scrapeId: string,
  selectedImageIndex: number,
): Promise<{ job_id: string }> => {
  const res = await fetch(`${BASE_URL}/process/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scrape_id: scrapeId, selected_image_index: selectedImageIndex }),
  })
  if (!res.ok) throw new Error('process_start_failed')
  return res.json()
}

export const createSSEConnection = (jobId: string): EventSource =>
  new EventSource(`${BASE_URL}/process/status/${jobId}`)
