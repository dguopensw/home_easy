import * as THREE from 'three'

/**
 * Create a reticle mesh for AR hit-test visualization.
 * Ring shape, blue color (#4fc3f7), semi-transparent, double-sided.
 * matrixAutoUpdate is disabled so the matrix can be set directly from hit test poses.
 */
export function createReticle(): THREE.Mesh {
  const geometry = new THREE.RingGeometry(0.08, 0.12, 32).rotateX(
    -Math.PI / 2,
  )
  const material = new THREE.MeshBasicMaterial({
    color: 0x4fc3f7,
    side: THREE.DoubleSide,
    opacity: 0.85,
    transparent: true,
  })

  const mesh = new THREE.Mesh(geometry, material)
  mesh.matrixAutoUpdate = false
  mesh.visible = false

  return mesh
}

/**
 * Update reticle position from XR hit test results.
 *
 * @param frame - The current XRFrame
 * @param hitTestSource - The active hit test source
 * @param referenceSpace - The local reference space
 * @param reticle - The reticle mesh to update
 * @returns true if a hit was detected, false otherwise
 */
export function updateReticle(
  frame: XRFrame,
  hitTestSource: XRHitTestSource,
  referenceSpace: XRReferenceSpace,
  reticle: THREE.Object3D,
): boolean {
  const hits = frame.getHitTestResults(hitTestSource)

  if (hits.length > 0) {
    const pose = hits[0].getPose(referenceSpace)
    if (pose) {
      reticle.visible = true
      reticle.matrix.fromArray(pose.transform.matrix)
      return true
    }
  }

  reticle.visible = false
  return false
}

/**
 * Dispose of reticle geometry and material resources.
 */
export function disposeReticle(reticle: THREE.Mesh): void {
  reticle.geometry?.dispose()
  const material = reticle.material
  if (Array.isArray(material)) {
    material.forEach((mat) => mat.dispose())
  } else if (material) {
    material.dispose()
  }
}
