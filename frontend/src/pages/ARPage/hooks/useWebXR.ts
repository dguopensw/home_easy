import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import type { ARSceneConfig, UseWebXRReturn } from '../types'
import {
  isWebXRSupported,
  startARSession,
  setupHitTest,
  cleanupARSession,
} from '../lib/xr-session'
import { loadGLB, applyDimensionScale, disposeModel } from '../lib/model-loader'
import { createReticle, updateReticle, disposeReticle } from '../lib/reticle'
import { checkPlaneCollisions } from '../lib/collision-detector'

/**
 * React hook that manages the full WebXR AR lifecycle:
 * session start/end, hit testing, reticle display, GLB loading,
 * dimension-based scaling, model placement, and cleanup.
 */
export function useWebXR(config: ARSceneConfig): UseWebXRReturn {
  const { canvasRef, overlayRef, glbUrl, dimensions } = config

  const [isSupported, setIsSupported] = useState(false)
  const [isSessionActive, setIsSessionActive] = useState(false)
  const [isModelPlaced, setIsModelPlaced] = useState(false)
  const [hasHitTest, setHasHitTest] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sessionRef = useRef<XRSession | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const modelRef = useRef<THREE.Object3D | null>(null)
  const reticleRef = useRef<THREE.Mesh | null>(null)
  const hitTestSourceRef = useRef<XRHitTestSource | null>(null)
  const referenceSpaceRef = useRef<XRReferenceSpace | null>(null)
  const dimensionsRef = useRef(dimensions)
  const isModelPlacedRef = useRef(false)
  const isCollidingRef = useRef(false)
  const originalMaterialsRef = useRef<Map<THREE.Mesh, THREE.Material | THREE.Material[]>>(new Map())
  const canvasRefInternal = canvasRef

  // Check WebXR support on mount
  useEffect(() => {
    isWebXRSupported().then(setIsSupported)
  }, [])

  const startSession = useCallback(async () => {
    const canvas = canvasRef.current
    const overlay = overlayRef.current
    if (!canvas || !overlay) {
      setError('Canvas or overlay element not found')
      return
    }

    try {
      setError(null)

      // 1. Start AR session
      const { session, renderer, scene, camera } = await startARSession(
        canvas,
        overlay,
      )
      sessionRef.current = session
      rendererRef.current = renderer
      sceneRef.current = scene
      cameraRef.current = camera

      // Listen for unexpected session end
      session.addEventListener('end', () => {
        cleanupRefs()
        setIsSessionActive(false)
        setIsModelPlaced(false)
        setHasHitTest(false)
      })

      // 2. Set up hit test (with one retry)
      let hitTestResult: Awaited<ReturnType<typeof setupHitTest>>
      try {
        hitTestResult = await setupHitTest(session)
      } catch {
        // Retry once
        hitTestResult = await setupHitTest(session)
      }
      hitTestSourceRef.current = hitTestResult.hitTestSource
      referenceSpaceRef.current = hitTestResult.referenceSpace

      // 3. Create reticle
      const reticle = createReticle()
      reticleRef.current = reticle
      scene.add(reticle)

      // 4. Load GLB model and apply dimension scale
      const model = await loadGLB(glbUrl)
      applyDimensionScale(model, dimensions)
      modelRef.current = model
      // Model is NOT added to scene until placeModel() is called

      // 5. Start render loop
      renderer.setAnimationLoop((_timestamp, frame) => {
        if (!frame) return

        // Update reticle from hit test only when model is not placed
        if (
          hitTestSourceRef.current &&
          referenceSpaceRef.current &&
          reticleRef.current &&
          !modelRef.current?.parent // model not in scene = not placed
        ) {
          const hit = updateReticle(
            frame,
            hitTestSourceRef.current,
            referenceSpaceRef.current,
            reticleRef.current,
          )
          setHasHitTest(hit)
        }

        // Collision detection — only when model is placed and plane-detection is available
        if (
          isModelPlacedRef.current &&
          modelRef.current &&
          referenceSpaceRef.current &&
          (frame as XRFrame & { detectedPlanes?: ReadonlySet<XRPlane> }).detectedPlanes
        ) {
          const detectedPlanes = (frame as XRFrame & { detectedPlanes: ReadonlySet<XRPlane> }).detectedPlanes
          const colliding = checkPlaneCollisions(
            modelRef.current,
            frame,
            referenceSpaceRef.current,
            detectedPlanes,
          )
          if (colliding !== isCollidingRef.current) {
            isCollidingRef.current = colliding
            if (colliding) {
              applyCollisionHighlight(modelRef.current)
            } else {
              restoreOriginalMaterials(modelRef.current, originalMaterialsRef.current)
            }
          }
        }

        renderer.render(scene, camera)
      })

      setIsSessionActive(true)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to start AR session'
      setError(message)
      cleanupRefs()
    }
  }, [canvasRef, overlayRef, glbUrl, dimensions])

  const cleanupRefs = useCallback(() => {
    // Dispose model
    if (modelRef.current) {
      disposeModel(modelRef.current)
      if (modelRef.current.parent) {
        modelRef.current.parent.remove(modelRef.current)
      }
      modelRef.current = null
    }

    // Dispose reticle
    if (reticleRef.current) {
      disposeReticle(reticleRef.current)
      if (reticleRef.current.parent) {
        reticleRef.current.parent.remove(reticleRef.current)
      }
      reticleRef.current = null
    }

    // Clean up session, renderer, hit test
    cleanupARSession(
      sessionRef.current,
      rendererRef.current,
      hitTestSourceRef.current,
    )
    sessionRef.current = null
    rendererRef.current = null
    sceneRef.current = null
    cameraRef.current = null
    hitTestSourceRef.current = null
    referenceSpaceRef.current = null
  }, [])

  const endSession = useCallback(() => {
    cleanupRefs()
    setIsSessionActive(false)
    setIsModelPlaced(false)
    setHasHitTest(false)
  }, [cleanupRefs])

  const placeModel = useCallback(() => {
    const reticle = reticleRef.current
    const model = modelRef.current
    const scene = sceneRef.current

    if (!reticle?.visible || !model || !scene) return

    // Extract world position from reticle matrix
    const position = new THREE.Vector3()
    const quaternion = new THREE.Quaternion()
    const scale = new THREE.Vector3()
    reticle.matrix.decompose(position, quaternion, scale)

    // Place model at reticle position, keep its y-offset for floor alignment
    model.position.set(position.x, position.y + model.position.y, position.z)
    scene.add(model)

    // Save original materials for collision highlight restore
    const origMap = originalMaterialsRef.current
    origMap.clear()
    model.traverse(child => {
      if (child instanceof THREE.Mesh) {
        origMap.set(child, child.material)
      }
    })

    // Hide reticle
    reticle.visible = false

    isModelPlacedRef.current = true
    setIsModelPlaced(true)
  }, [])

  const resetModel = useCallback(() => {
    const model = modelRef.current
    const scene = sceneRef.current
    const reticle = reticleRef.current

    if (!model || !scene) return

    // Restore original materials before removing
    restoreOriginalMaterials(model, originalMaterialsRef.current)
    isCollidingRef.current = false

    scene.remove(model)

    if (reticle) {
      reticle.visible = true
    }

    isModelPlacedRef.current = false
    setIsModelPlaced(false)
  }, [])

  const getPlacedModel = useCallback((): THREE.Object3D | null => {
    return modelRef.current
  }, [])

  const applyNewDimensions = useCallback((dims: { w: number; h: number; d: number }) => {
    const model = modelRef.current
    if (!model) return
    const prevElevation = model.position.y
    applyDimensionScale(model, dims)
    model.position.y = prevElevation
    dimensionsRef.current = dims
    // Refresh original materials after rescale
    const origMap = originalMaterialsRef.current
    origMap.clear()
    model.traverse(child => {
      if (child instanceof THREE.Mesh) {
        origMap.set(child, child.material)
      }
    })
    isCollidingRef.current = false
  }, [])

  const captureAndShare = useCallback(async () => {
    const canvas = canvasRefInternal.current
    if (!canvas) return
    canvas.toBlob(async (blob) => {
      if (!blob) return
      const file = new File([blob], 'ar-furniture.png', { type: 'image/png' })
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: '가구 AR 배치 결과' })
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'ar-furniture.png'
        a.click()
        URL.revokeObjectURL(url)
      }
    }, 'image/png')
  }, [canvasRefInternal])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupRefs()
    }
  }, [cleanupRefs])

  return {
    isSupported,
    isSessionActive,
    isModelPlaced,
    hasHitTest,
    error,
    startSession,
    endSession,
    placeModel,
    resetModel,
    getPlacedModel,
    applyNewDimensions,
    captureAndShare,
  }
}

// ─── Collision highlight helpers ───

function applyCollisionHighlight(model: THREE.Object3D): void {
  model.traverse(child => {
    if (!(child instanceof THREE.Mesh)) return
    const mat = (child.material as THREE.Material).clone() as THREE.MeshStandardMaterial
    if ('emissive' in mat) {
      mat.emissive.set(0xff0000)
      mat.emissiveIntensity = 0.6
    }
    child.material = mat
  })
}

function restoreOriginalMaterials(
  model: THREE.Object3D,
  origMap: Map<THREE.Mesh, THREE.Material | THREE.Material[]>,
): void {
  model.traverse(child => {
    if (!(child instanceof THREE.Mesh)) return
    const orig = origMap.get(child)
    if (orig) child.material = orig
  })
}
