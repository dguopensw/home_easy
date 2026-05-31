import * as THREE from 'three'

/**
 * Check whether the placed model's AABB penetrates any detected XR planes.
 *
 * Returns true if any corner of the model bounding box lies behind any plane
 * by more than the tolerance threshold (2 cm).
 */
export function checkPlaneCollisions(
  model: THREE.Object3D,
  frame: XRFrame,
  referenceSpace: XRReferenceSpace,
  detectedPlanes: ReadonlySet<XRPlane>,
): boolean {
  const modelBox = new THREE.Box3().setFromObject(model)
  const corners = getBox3Corners(modelBox)

  for (const plane of detectedPlanes) {
    const planePose = frame.getPose(plane.planeSpace, referenceSpace)
    if (!planePose) continue

    const planeMatrix = new THREE.Matrix4().fromArray(planePose.transform.matrix)
    const normal = new THREE.Vector3(0, 1, 0).applyMatrix4(planeMatrix).normalize()
    const origin = new THREE.Vector3().setFromMatrixPosition(planeMatrix)

    const penetrates = corners.some(
      c => c.clone().sub(origin).dot(normal) < -0.02,
    )
    if (penetrates) return true
  }
  return false
}

function getBox3Corners(box: THREE.Box3): THREE.Vector3[] {
  const { min, max } = box
  return [
    new THREE.Vector3(min.x, min.y, min.z),
    new THREE.Vector3(max.x, min.y, min.z),
    new THREE.Vector3(min.x, max.y, min.z),
    new THREE.Vector3(max.x, max.y, min.z),
    new THREE.Vector3(min.x, min.y, max.z),
    new THREE.Vector3(max.x, min.y, max.z),
    new THREE.Vector3(min.x, max.y, max.z),
    new THREE.Vector3(max.x, max.y, max.z),
  ]
}
