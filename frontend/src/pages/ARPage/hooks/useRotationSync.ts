import { useState } from 'react'
import * as THREE from 'three'

export function useRotationSync(getPlacedModel: () => THREE.Object3D | null) {
  const [rotationDeg, setRotationDeg] = useState(0)

  const setRotationY = (deg: number) => {
    const model = getPlacedModel()
    if (model) model.rotation.y = (deg * Math.PI) / 180
    setRotationDeg(deg)
  }

  const onRotationChange = (radians: number) => {
    const normalized = ((radians * 180) / Math.PI % 360 + 360) % 360
    setRotationDeg(normalized)
  }

  return { rotationDeg, setRotationY, onRotationChange }
}
