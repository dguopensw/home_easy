/**
 * useARGestures.ts
 *
 * React hook that wires gesture-handler to the DOM overlay element
 * and exposes button control callbacks for ARControls.
 */

import { useEffect, useRef, useMemo, type RefObject } from 'react';
import type * as THREE from 'three';
import {
  createGestureState,
  handleTouchStart,
  handleTouchMove,
  handleTouchEnd,
  createButtonControls,
} from '../lib/gesture-handler';

// ─── Types ───

export interface UseARGesturesOptions {
  overlayRef: RefObject<HTMLDivElement>;
  getPlacedModel: () => THREE.Object3D | null;
  isModelPlaced: boolean;
  onRotationChange?: (radians: number) => void;
}

export interface UseARGesturesReturn {
  rotateLeft: () => void;
  rotateRight: () => void;
  liftUp: () => void;
  liftDown: () => void;
  scaleUp: () => void;
  scaleDown: () => void;
  setRotationY: (radians: number) => void;
}

// ─── Hook ───

export function useARGestures({
  overlayRef,
  getPlacedModel,
  isModelPlaced,
  onRotationChange,
}: UseARGesturesOptions): UseARGesturesReturn {
  const gestureStateRef = useRef(createGestureState());

  // Register / unregister touch listeners on the overlay element.
  // Re-registers when isModelPlaced changes so handlers capture the latest flag.
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;

    const onTouchStart = (e: TouchEvent): void => {
      if (!isModelPlaced) return;
      handleTouchStart(e, gestureStateRef.current);
    };

    const onTouchMove = (e: TouchEvent): void => {
      if (!isModelPlaced) return;
      handleTouchMove(e, gestureStateRef.current, getPlacedModel(), onRotationChange);
    };

    const onTouchEnd = (e: TouchEvent): void => {
      if (!isModelPlaced) return;
      handleTouchEnd(e, gestureStateRef.current);
    };

    overlay.addEventListener('touchstart', onTouchStart, { passive: false });
    overlay.addEventListener('touchmove', onTouchMove, { passive: false });
    overlay.addEventListener('touchend', onTouchEnd);

    return () => {
      overlay.removeEventListener('touchstart', onTouchStart);
      overlay.removeEventListener('touchmove', onTouchMove);
      overlay.removeEventListener('touchend', onTouchEnd);
    };
  }, [isModelPlaced, overlayRef, getPlacedModel, onRotationChange]);

  // Button controls are stable across renders because getPlacedModel
  // is expected to be a stable reference (e.g. useCallback in the parent).
  const buttons = useMemo(
    () => createButtonControls(getPlacedModel),
    [getPlacedModel],
  );

  const rotateLeft = useMemo(() => () => {
    buttons.rotateLeft();
    const model = getPlacedModel();
    if (model) onRotationChange?.(model.rotation.y);
  }, [buttons, getPlacedModel, onRotationChange]);

  const rotateRight = useMemo(() => () => {
    buttons.rotateRight();
    const model = getPlacedModel();
    if (model) onRotationChange?.(model.rotation.y);
  }, [buttons, getPlacedModel, onRotationChange]);

  const setRotationY = useMemo(() => (radians: number) => {
    const model = getPlacedModel();
    if (model) model.rotation.y = radians;
  }, [getPlacedModel]);

  return {
    rotateLeft,
    rotateRight,
    liftUp: buttons.liftUp,
    liftDown: buttons.liftDown,
    scaleUp: buttons.scaleUp,
    scaleDown: buttons.scaleDown,
    setRotationY,
  };
}
