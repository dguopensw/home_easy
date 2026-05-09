const BASE_URL = import.meta.env.VITE_API_URL

export const startGeneration = async (url: string): Promise<{ job_id: string }> => {
  const res = await fetch(`${BASE_URL}/furniture/gen/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error('generation_failed')
  return res.json()
}

export const createSSEConnection = (jobId: string): EventSource =>
  new EventSource(`${BASE_URL}/furniture/gen/status/${jobId}`)
