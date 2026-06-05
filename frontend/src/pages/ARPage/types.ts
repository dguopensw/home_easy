import type * as THREE from 'three'

// --- Router State ---
export interface ARRouteState {
  glbUrl: string
  dimensions: { w: number; h: number; d: number } // cm
  sourceUrl: string
}

// --- Scene Config ---
export interface ARSceneConfig {
  glbUrl: string
  dimensions: { w: number; h: number; d: number } // cm
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  overlayRef: React.RefObject<HTMLDivElement | null>
}

// --- Placement State ---
export interface ARPlacementState {
  isPlaced: boolean
  position: { x: number; y: number; z: number }
  rotationY: number // radians
  scale: number // uniform scale multiplier (1.0 = original)
  elevationY: number // Y offset from floor (m)
}

// --- useWebXR Return ---
export interface UseWebXRReturn {
  // State
  isSupported: boolean
  isSessionActive: boolean
  isModelPlaced: boolean
  hasHitTest: boolean
  error: string | null

  // Actions
  startSession: () => Promise<void>
  endSession: () => void
  placeModel: () => void
  resetModel: () => void

  // Internal Three.js object access (for Interaction builder)
  getPlacedModel: () => THREE.Object3D | null

  // Extended actions
  applyNewDimensions: (dims: { w: number; h: number; d: number }) => void
  captureAndShare: () => Promise<void>
}

// --- useARGestures Return ---
export interface UseARGesturesReturn {
  rotationY: number
  scaleFactor: number
  elevationY: number

  rotateLeft: () => void
  rotateRight: () => void
  scaleUp: () => void
  scaleDown: () => void
  moveUp: () => void
  moveDown: () => void
  resetTransform: () => void

  handlers: {
    onTouchStart: (e: TouchEvent) => void
    onTouchMove: (e: TouchEvent) => void
    onTouchEnd: (e: TouchEvent) => void
  }
}

// --- Platform Detection ---
export type ARPlatform = 'android-webxr' | 'ios-quicklook' | 'unsupported'
