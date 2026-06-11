import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'

const DRACO_DECODER_PATH =
  'https://www.gstatic.com/draco/versioned/decoders/1.5.6/'

export interface DimensionsCm {
  width: number
  height: number
  depth: number
}

/**
 * Load a normalized GLB (correct proportions, arbitrary size), uniformly
 * scale it up to its real-world dimensions, bake the scale into the scene,
 * and re-export as a binary GLB Blob.
 *
 * The resulting GLB carries the correct real-world size in its own units,
 * so <model-viewer>'s Scene Viewer / Quick Look AR shows it at true scale
 * without any backend change.
 *
 * @param glbUrl Source GLB URL
 * @param dims   Target real dimensions in centimeters { width, height, depth }
 * @returns      Object URL of the rescaled GLB (caller must revoke it)
 */
export async function rescaleGlbToBlobUrl(
  glbUrl: string,
  dims: DimensionsCm,
): Promise<string> {
  const loader = new GLTFLoader()
  const dracoLoader = new DRACOLoader()
  dracoLoader.setDecoderPath(DRACO_DECODER_PATH)
  loader.setDRACOLoader(dracoLoader)

  let scene: THREE.Group
  try {
    const gltf = await loader.loadAsync(glbUrl)
    scene = gltf.scene
  } finally {
    dracoLoader.dispose()
  }

  applyUniformScale(scene, dims)

  const exporter = new GLTFExporter()
  const glbArrayBuffer = (await exporter.parseAsync(scene, {
    binary: true,
  })) as ArrayBuffer

  const blob = new Blob([glbArrayBuffer], { type: 'model/gltf-binary' })
  return URL.createObjectURL(blob)
}

/**
 * Uniformly scale an object so its bounding box matches the target real-world
 * dimensions, assuming proportions are already correct. The single scale
 * factor is the average of the per-axis ratios, which cancels small
 * proportion noise instead of stretching the model. Bottom is aligned to y=0.
 */
function applyUniformScale(object: THREE.Object3D, dims: DimensionsCm): void {
  object.scale.set(1, 1, 1)
  object.updateMatrixWorld(true)

  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())
  if (size.x === 0 || size.y === 0 || size.z === 0) return

  // cm → meters
  const targetM = {
    w: dims.width / 100,
    h: dims.height / 100,
    d: dims.depth / 100,
  }

  // Per-axis ratios should be ~equal when proportions are correct;
  // average them so minor mismatches don't distort the model.
  const factor =
    (targetM.w / size.x + targetM.h / size.y + targetM.d / size.z) / 3

  object.scale.setScalar(factor)

  // Align bottom to y=0 so it sits on the AR floor plane
  object.updateMatrixWorld(true)
  const boxAfter = new THREE.Box3().setFromObject(object)
  object.position.y -= boxAfter.min.y
}
