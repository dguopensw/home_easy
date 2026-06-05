import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'

const DRACO_DECODER_PATH =
  'https://www.gstatic.com/draco/versioned/decoders/1.5.6/'

/**
 * Load a GLB model with optional Draco decompression support.
 *
 * @param url - URL of the GLB file
 * @returns The loaded model as a THREE.Group
 */
export async function loadGLB(url: string): Promise<THREE.Group> {
  const loader = new GLTFLoader()

  const dracoLoader = new DRACOLoader()
  dracoLoader.setDecoderPath(DRACO_DECODER_PATH)
  loader.setDRACOLoader(dracoLoader)

  return new Promise<THREE.Group>((resolve, reject) => {
    loader.load(
      url,
      (gltf) => {
        dracoLoader.dispose()
        resolve(gltf.scene)
      },
      undefined,
      (error) => {
        dracoLoader.dispose()
        reject(
          error instanceof Error
            ? error
            : new Error(`Failed to load GLB: ${String(error)}`),
        )
      },
    )
  })
}

/**
 * Scale a model to fit within target dimensions while preserving aspect ratio.
 * After scaling, the model bottom is aligned to y=0.
 *
 * @param object - The Three.js object to scale
 * @param targetCm - Target dimensions in centimeters { w, h, d }
 */
export function applyDimensionScale(
  object: THREE.Object3D,
  targetCm: { w: number; h: number; d: number },
): void {
  // Reset scale to measure original bounding box
  object.scale.set(1, 1, 1)
  object.updateMatrixWorld(true)

  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())

  // Guard against degenerate models
  if (size.x === 0 || size.y === 0 || size.z === 0) return

  // Convert cm to meters
  const targetM = {
    w: targetCm.w / 100,
    h: targetCm.h / 100,
    d: targetCm.d / 100,
  }

  // Scale each axis independently to match exact target dimensions
  const sx = targetM.w / size.x
  const sy = targetM.h / size.y
  const sz = targetM.d / size.z

  object.scale.set(sx, sy, sz)

  // Align model bottom to y=0
  object.updateMatrixWorld(true)
  const boxAfter = new THREE.Box3().setFromObject(object)
  object.position.y -= boxAfter.min.y
}

/**
 * Dispose of all geometries and materials in a Three.js object tree.
 *
 * @param object - Root object to traverse and dispose
 */
export function disposeModel(object: THREE.Object3D): void {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry?.dispose()
      const material = child.material
      if (Array.isArray(material)) {
        material.forEach((mat) => mat.dispose())
      } else if (material) {
        material.dispose()
      }
    }
  })
}
