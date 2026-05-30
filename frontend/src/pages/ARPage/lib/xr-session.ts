import * as THREE from 'three'

/**
 * Check if the browser supports WebXR immersive-ar sessions.
 */
export async function isWebXRSupported(): Promise<boolean> {
  if (!navigator.xr) return false
  try {
    return await navigator.xr.isSessionSupported('immersive-ar')
  } catch {
    return false
  }
}

/**
 * Start a WebXR immersive-ar session with hit-test support.
 *
 * @param canvas - The HTMLCanvasElement to render into
 * @param overlayEl - The HTMLElement used as DOM overlay root
 * @returns The XR session, renderer, scene, and camera
 */
export async function startARSession(
  canvas: HTMLCanvasElement,
  overlayEl: HTMLElement,
): Promise<{
  session: XRSession
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
}> {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    preserveDrawingBuffer: true,
  })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.xr.enabled = true

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(
    70,
    window.innerWidth / window.innerHeight,
    0.01,
    20,
  )

  // Add ambient + directional light for model visibility
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.8)
  scene.add(ambientLight)
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6)
  directionalLight.position.set(0.5, 1, 0.5)
  scene.add(directionalLight)

  const session = await navigator.xr!.requestSession('immersive-ar', {
    requiredFeatures: ['hit-test'],
    optionalFeatures: ['dom-overlay', 'plane-detection'],
    domOverlay: { root: overlayEl },
  })

  await renderer.xr.setSession(session)

  return { session, renderer, scene, camera }
}

/**
 * Set up a hit test source from the viewer reference space.
 *
 * @param session - The active XR session
 * @returns The hit test source and local reference space
 */
export async function setupHitTest(session: XRSession): Promise<{
  hitTestSource: XRHitTestSource
  referenceSpace: XRReferenceSpace
}> {
  const viewerSpace = await session.requestReferenceSpace('viewer')
  const hitTestSource = await session.requestHitTestSource!({
    space: viewerSpace,
  })

  if (!hitTestSource) {
    throw new Error('Failed to create hit test source')
  }

  const referenceSpace = await session.requestReferenceSpace('local')

  return { hitTestSource, referenceSpace }
}

/**
 * Clean up AR session resources. Safe to call with null values.
 */
export function cleanupARSession(
  session: XRSession | null,
  renderer: THREE.WebGLRenderer | null,
  hitTestSource: XRHitTestSource | null,
): void {
  hitTestSource?.cancel()
  renderer?.setAnimationLoop(null)
  renderer?.dispose()
  session?.end().catch(() => {
    // Session may already have ended; ignore
  })
}
