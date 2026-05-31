/**
 * gesture-handler.ts
 *
 * Pure gesture state management for WebAR touch interactions.
 * No React dependency — consumed by useARGestures hook.
 */

import type * as THREE from 'three';

// ─── Constants ───

export const ROTATION_SPEED = 0.008; // rad/px
export const MIN_SCALE = 0.1;
export const MAX_SCALE = 5.0;
const ROTATE_STEP = Math.PI / 8; // 22.5 deg
const LIFT_STEP = 0.05; // 5 cm
const LIFT_MAX = 2.0; // m
const LIFT_MIN = 0.0; // m
const SCALE_UP_FACTOR = 1.1;
const SCALE_DOWN_FACTOR = 0.9;

// ─── Types ───

export interface GestureState {
  isDragging: boolean;
  lastTouchX: number;
  isPinching: boolean;
  lastPinchDist: number;
}

export interface ButtonControls {
  rotateLeft: () => void;
  rotateRight: () => void;
  liftUp: () => void;
  liftDown: () => void;
  scaleUp: () => void;
  scaleDown: () => void;
}

// ─── Helpers ───

export function createGestureState(): GestureState {
  return {
    isDragging: false,
    lastTouchX: 0,
    isPinching: false,
    lastPinchDist: 0,
  };
}

function getPinchDist(e: TouchEvent): number {
  return Math.hypot(
    e.touches[1].clientX - e.touches[0].clientX,
    e.touches[1].clientY - e.touches[0].clientY,
  );
}

// ─── Touch Handlers ───

export function handleTouchStart(e: TouchEvent, state: GestureState): void {
  if (e.touches.length === 1) {
    state.isDragging = true;
    state.lastTouchX = e.touches[0].clientX;
  } else if (e.touches.length === 2) {
    state.isPinching = true;
    state.isDragging = false;
    state.lastPinchDist = getPinchDist(e);
  }
}

export function handleTouchMove(
  e: TouchEvent,
  state: GestureState,
  model: THREE.Object3D | null,
  onRotationChange?: (y: number) => void,
): void {
  if (!model) return;

  if (e.touches.length === 1 && state.isDragging && !state.isPinching) {
    const dx = e.touches[0].clientX - state.lastTouchX;
    model.rotation.y += dx * ROTATION_SPEED;
    state.lastTouchX = e.touches[0].clientX;
    onRotationChange?.(model.rotation.y);
    e.preventDefault();
  }

  if (e.touches.length === 2 && state.isPinching) {
    const dist = getPinchDist(e);
    if (state.lastPinchDist > 0) {
      const ratio = dist / state.lastPinchDist;
      const newScale = Math.max(
        MIN_SCALE,
        Math.min(MAX_SCALE, model.scale.x * ratio),
      );
      model.scale.setScalar(newScale);
    }
    state.lastPinchDist = dist;
    e.preventDefault();
  }
}

export function handleTouchEnd(e: TouchEvent, state: GestureState): void {
  if (e.touches.length < 2) {
    state.isPinching = false;
    state.lastPinchDist = 0;
  }
  if (e.touches.length === 0) {
    state.isDragging = false;
  }
}

// ─── Button Controls Factory ───

export function createButtonControls(
  getModel: () => THREE.Object3D | null,
): ButtonControls {
  const withModel = (fn: (m: THREE.Object3D) => void): (() => void) => {
    return () => {
      const m = getModel();
      if (m) fn(m);
    };
  };

  return {
    rotateLeft: withModel((m) => {
      m.rotation.y -= ROTATE_STEP;
    }),
    rotateRight: withModel((m) => {
      m.rotation.y += ROTATE_STEP;
    }),
    liftUp: withModel((m) => {
      m.position.y = Math.min(m.position.y + LIFT_STEP, LIFT_MAX);
    }),
    liftDown: withModel((m) => {
      m.position.y = Math.max(m.position.y - LIFT_STEP, LIFT_MIN);
    }),
    scaleUp: withModel((m) => {
      const newScale = Math.min(MAX_SCALE, m.scale.x * SCALE_UP_FACTOR);
      m.scale.setScalar(newScale);
    }),
    scaleDown: withModel((m) => {
      const newScale = Math.max(MIN_SCALE, m.scale.x * SCALE_DOWN_FACTOR);
      m.scale.setScalar(newScale);
    }),
  };
}
