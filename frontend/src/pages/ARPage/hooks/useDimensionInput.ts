import { useState } from 'react'

export interface Dimensions {
  w: number
  h: number
  d: number
}

export function useDimensionInput(
  initialDims: Dimensions,
  onApply: (dims: Dimensions) => void,
) {
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [draft, setDraft] = useState<Dimensions>(initialDims)

  const openPanel = () => {
    setDraft(initialDims)
    setIsPanelOpen(true)
  }

  const applyDimensions = () => {
    onApply(draft)
    setIsPanelOpen(false)
  }

  return { isPanelOpen, openPanel, setIsPanelOpen, draft, setDraft, applyDimensions }
}
