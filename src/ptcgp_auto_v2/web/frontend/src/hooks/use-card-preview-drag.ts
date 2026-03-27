import { type MutableRefObject, type PointerEvent as ReactPointerEvent, useCallback, useEffect, useRef, useState } from 'react'

// 拖拽 X 轴旋转上限（上下倾斜）
const PREVIEW_ROTATE_X_LIMIT = 30
// 拖拽 Y 轴旋转上限（左右翻转，超过 90 才能看到卡背）
const PREVIEW_ROTATE_Y_LIMIT = 170
// requestAnimationFrame 插值比例：每帧逼近目标 15%
const PREVIEW_LERP_FACTOR = 0.15
// 拖拽中使用更高插值，保证跟手
const PREVIEW_DRAG_LERP_FACTOR = 0.82
// 开启 idle 漂浮：静置时模拟自然漂浮
const PREVIEW_ENABLE_IDLE_FLOAT = true
// 进场动画约 1650ms，静置漂浮必须晚于进场结束，避免抢同一条 transform
const PREVIEW_IDLE_DELAY_MS = 2200
// 插值收敛阈值：低于该阈值时停帧
const PREVIEW_SETTLE_ROTATE_EPSILON = 0.02
const PREVIEW_SETTLE_POINTER_EPSILON = 0.0008
// 样式写入阈值：避免高频写入导致主线程压力
const PREVIEW_APPLY_EPSILON = 0.0006
// 拖拽启动阈值：防止按下瞬间就发生倾斜跳变
const PREVIEW_DRAG_START_DISTANCE_PX = 3

interface PreviewPointerMetrics {
  ratioX: number
  ratioY: number
  fromCenterX: number
  fromCenterY: number
}

interface PreviewRect {
  left: number
  top: number
  width: number
  height: number
}

interface PreviewVisualState {
  rotateX: number
  rotateY: number
  pointer: PreviewPointerMetrics
}

interface AppliedVisualSnapshot {
  pointerX: number
  pointerY: number
  fromCenterX: number
  fromCenterY: number
  pointerDistance: number
  rotateX: number
  rotateY: number
  tiltStrength: number
  holoAngle: number
}

interface PreviewDragState {
  dragging: boolean
  pointerId: number
  anchorRect: PreviewRect | null
  pressX: number
  pressY: number
  pressPointer: PreviewPointerMetrics
  startRotateX: number
  startRotateY: number
  moved: boolean
  targetRotateX: number
  targetRotateY: number
  targetPointer: PreviewPointerMetrics
}

interface UseCardPreviewDragResult {
  cardRef: MutableRefObject<HTMLDivElement | null>
  shineRef: MutableRefObject<HTMLDivElement | null>
  dragging: boolean
  startDrag: (event: ReactPointerEvent<HTMLDivElement>) => void
  onDragMove: (event: ReactPointerEvent<HTMLDivElement>) => void
  stopDrag: (withRebound?: boolean) => void
  resetTransform: (animated?: boolean) => void
}

const DEFAULT_POINTER_METRICS: PreviewPointerMetrics = {
  ratioX: 0.5,
  ratioY: 0.5,
  fromCenterX: 0,
  fromCenterY: 0
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) {
    return min
  }
  if (value > max) {
    return max
  }
  return value
}

function resolvePointerMetrics(
  cardEl: HTMLDivElement | null,
  clientX: number,
  clientY: number
): PreviewPointerMetrics {
  const rect = cardEl?.getBoundingClientRect()
  if (!rect) {
    return DEFAULT_POINTER_METRICS
  }
  return resolvePointerMetricsFromRect(rect, clientX, clientY)
}

function resolvePointerMetricsFromRect(
  rect: PreviewRect,
  clientX: number,
  clientY: number
): PreviewPointerMetrics {
  if (rect.width <= 0 || rect.height <= 0) {
    return DEFAULT_POINTER_METRICS
  }

  const ratioX = clamp((clientX - rect.left) / rect.width, 0, 1)
  const ratioY = clamp((clientY - rect.top) / rect.height, 0, 1)

  return {
    ratioX,
    ratioY,
    fromCenterX: ratioX * 2 - 1,
    fromCenterY: ratioY * 2 - 1
  }
}

function clonePointer(pointer: PreviewPointerMetrics): PreviewPointerMetrics {
  return {
    ratioX: pointer.ratioX,
    ratioY: pointer.ratioY,
    fromCenterX: pointer.fromCenterX,
    fromCenterY: pointer.fromCenterY
  }
}

function resolveIdleFloatHost(cardEl: HTMLDivElement | null): HTMLElement | null {
  if (!cardEl) {
    return null
  }
  const parent = cardEl.parentElement
  if (!parent) {
    return cardEl
  }
  if (parent.classList.contains('card-preview-motion') || parent.classList.contains('owned-card-preview-motion')) {
    return parent
  }
  return cardEl
}

export function useCardPreviewDrag(): UseCardPreviewDragResult {
  const [dragging, setDragging] = useState(false)
  const cardRef = useRef<HTMLDivElement | null>(null)
  const shineRef = useRef<HTMLDivElement | null>(null)
  const windowListenersAttachedRef = useRef(false)
  const prefersReducedMotionRef = useRef(false)
  const idleTimerRef = useRef<number | null>(null)
  const idleActiveRef = useRef(false)
  const animationFrameRef = useRef<number | null>(null)
  const stopDragRef = useRef<(withRebound?: boolean) => void>(() => {})
  const appliedSnapshotRef = useRef<AppliedVisualSnapshot | null>(null)
  const captureHostRef = useRef<HTMLDivElement | null>(null)

  const dragStateRef = useRef<PreviewDragState>({
    dragging: false,
    pointerId: -1,
    anchorRect: null,
    pressX: 0,
    pressY: 0,
    pressPointer: clonePointer(DEFAULT_POINTER_METRICS),
    startRotateX: 0,
    startRotateY: 0,
    moved: false,
    targetRotateX: 0,
    targetRotateY: 0,
    targetPointer: clonePointer(DEFAULT_POINTER_METRICS)
  })

  const renderStateRef = useRef<PreviewVisualState>({
    rotateX: 0,
    rotateY: 0,
    pointer: clonePointer(DEFAULT_POINTER_METRICS)
  })

  const applyVisualState = useCallback((state: PreviewVisualState): void => {
    const cardEl = cardRef.current
    const shineEl = shineRef.current

    const pointerDistance = Math.min(1, Math.hypot(state.pointer.fromCenterX, state.pointer.fromCenterY))
    const rotateDistance = Math.min(1, (Math.abs(state.rotateX) + Math.abs(state.rotateY)) / (PREVIEW_ROTATE_X_LIMIT + PREVIEW_ROTATE_Y_LIMIT))
    const tiltStrength = clamp(pointerDistance * 0.45 + rotateDistance * 0.85, 0, 1)
    const holoAngle = ((Math.atan2(state.pointer.fromCenterY, state.pointer.fromCenterX) * 180) / Math.PI + 450) % 360

    const snapshot: AppliedVisualSnapshot = {
      pointerX: state.pointer.ratioX,
      pointerY: state.pointer.ratioY,
      fromCenterX: state.pointer.fromCenterX,
      fromCenterY: state.pointer.fromCenterY,
      pointerDistance,
      rotateX: state.rotateX,
      rotateY: state.rotateY,
      tiltStrength,
      holoAngle
    }
    const previous = appliedSnapshotRef.current
    const changed = !previous
      || Math.abs(previous.pointerX - snapshot.pointerX) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.pointerY - snapshot.pointerY) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.fromCenterX - snapshot.fromCenterX) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.fromCenterY - snapshot.fromCenterY) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.pointerDistance - snapshot.pointerDistance) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.rotateX - snapshot.rotateX) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.rotateY - snapshot.rotateY) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.tiltStrength - snapshot.tiltStrength) > PREVIEW_APPLY_EPSILON
      || Math.abs(previous.holoAngle - snapshot.holoAngle) > 0.08

    if (!changed) {
      return
    }
    appliedSnapshotRef.current = snapshot

    const pointerX = `${(snapshot.pointerX * 100).toFixed(3)}%`
    const pointerY = `${(snapshot.pointerY * 100).toFixed(3)}%`

    if (cardEl) {
      cardEl.style.setProperty('--preview-pointer-x', pointerX)
      cardEl.style.setProperty('--preview-pointer-y', pointerY)
      cardEl.style.setProperty('--preview-glare-x', pointerX)
      cardEl.style.setProperty('--preview-glare-y', pointerY)
      cardEl.style.setProperty('--preview-pointer-from-center-x', snapshot.fromCenterX.toFixed(4))
      cardEl.style.setProperty('--preview-pointer-from-center-y', snapshot.fromCenterY.toFixed(4))
      cardEl.style.setProperty('--preview-pointer-from-center', snapshot.pointerDistance.toFixed(4))
      cardEl.style.setProperty('--preview-rotate-x', `${snapshot.rotateX.toFixed(3)}deg`)
      cardEl.style.setProperty('--preview-rotate-y', `${snapshot.rotateY.toFixed(3)}deg`)
      cardEl.style.setProperty('--preview-tilt-strength', snapshot.tiltStrength.toFixed(4))
      cardEl.style.setProperty('--preview-holo-angle', `${snapshot.holoAngle.toFixed(2)}deg`)
    }

    if (shineEl) {
      shineEl.style.setProperty('--preview-glare-x', pointerX)
      shineEl.style.setProperty('--preview-glare-y', pointerY)
      shineEl.style.setProperty('--preview-pointer-from-center', snapshot.pointerDistance.toFixed(4))
    }
  }, [])

  const syncRenderToTarget = useCallback((): void => {
    const dragState = dragStateRef.current
    const renderState = renderStateRef.current

    renderState.rotateX = dragState.targetRotateX
    renderState.rotateY = dragState.targetRotateY
    renderState.pointer = clonePointer(dragState.targetPointer)
  }, [])

  const setTargetNeutral = useCallback((): void => {
    const dragState = dragStateRef.current
    dragState.targetRotateX = 0
    dragState.targetRotateY = 0
    dragState.targetPointer = clonePointer(DEFAULT_POINTER_METRICS)
  }, [])

  const clearIdleTimer = useCallback((): void => {
    if (idleTimerRef.current === null) {
      return
    }
    window.clearTimeout(idleTimerRef.current)
    idleTimerRef.current = null
  }, [])

  const stopIdleFloat = useCallback((): void => {
    if (!idleActiveRef.current) {
      return
    }
    idleActiveRef.current = false
    const cardEl = cardRef.current
    const hostEl = resolveIdleFloatHost(cardEl)
    if (!hostEl) {
      return
    }
    hostEl.classList.remove('preview-idle-float')
    hostEl.removeAttribute('data-preview-idle-variant')
    cardEl?.classList.remove('preview-idle-float')
    cardEl?.removeAttribute('data-preview-idle-variant')
  }, [])

  const startIdleFloat = useCallback((): void => {
    if (!PREVIEW_ENABLE_IDLE_FLOAT) {
      return
    }
    if (prefersReducedMotionRef.current) {
      return
    }
    const dragState = dragStateRef.current
    if (dragState.dragging) {
      return
    }
    const cardEl = cardRef.current
    const hostEl = resolveIdleFloatHost(cardEl)
    if (!hostEl) {
      return
    }
    idleActiveRef.current = true
    const idleVariant = String(Math.floor(Math.random() * 3) + 1)
    hostEl.setAttribute('data-preview-idle-variant', idleVariant)
    hostEl.classList.add('preview-idle-float')
  }, [])

  const scheduleIdleFloat = useCallback((): void => {
    clearIdleTimer()
    if (!PREVIEW_ENABLE_IDLE_FLOAT) {
      return
    }
    if (prefersReducedMotionRef.current) {
      return
    }
    idleTimerRef.current = window.setTimeout(() => {
      idleTimerRef.current = null
      startIdleFloat()
    }, PREVIEW_IDLE_DELAY_MS)
  }, [clearIdleTimer, startIdleFloat])

  const markInteraction = useCallback((): void => {
    stopIdleFloat()
    scheduleIdleFloat()
  }, [scheduleIdleFloat, stopIdleFloat])

  const setAnimatingClass = useCallback((active: boolean): void => {
    const cardEl = cardRef.current
    if (!cardEl) {
      return
    }
    if (active) {
      cardEl.classList.add('preview-animating')
      return
    }
    cardEl.classList.remove('preview-animating')
  }, [])

  const stepAnimation = useCallback((): void => {
    const dragState = dragStateRef.current
    const renderState = renderStateRef.current
    const lerpFactor = dragState.dragging ? PREVIEW_DRAG_LERP_FACTOR : PREVIEW_LERP_FACTOR

    renderState.rotateX += (dragState.targetRotateX - renderState.rotateX) * lerpFactor
    renderState.rotateY += (dragState.targetRotateY - renderState.rotateY) * lerpFactor
    renderState.pointer.ratioX += (dragState.targetPointer.ratioX - renderState.pointer.ratioX) * lerpFactor
    renderState.pointer.ratioY += (dragState.targetPointer.ratioY - renderState.pointer.ratioY) * lerpFactor
    renderState.pointer.fromCenterX += (dragState.targetPointer.fromCenterX - renderState.pointer.fromCenterX) * lerpFactor
    renderState.pointer.fromCenterY += (dragState.targetPointer.fromCenterY - renderState.pointer.fromCenterY) * lerpFactor

    if (cardRef.current || shineRef.current) {
      applyVisualState(renderState)
    }

    const rotateSettled = Math.abs(dragState.targetRotateX - renderState.rotateX) <= PREVIEW_SETTLE_ROTATE_EPSILON
      && Math.abs(dragState.targetRotateY - renderState.rotateY) <= PREVIEW_SETTLE_ROTATE_EPSILON
    const pointerSettled = Math.abs(dragState.targetPointer.ratioX - renderState.pointer.ratioX) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.ratioY - renderState.pointer.ratioY) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.fromCenterX - renderState.pointer.fromCenterX) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.fromCenterY - renderState.pointer.fromCenterY) <= PREVIEW_SETTLE_POINTER_EPSILON

    if (dragState.dragging || !rotateSettled || !pointerSettled) {
      animationFrameRef.current = window.requestAnimationFrame(stepAnimation)
      return
    }

    animationFrameRef.current = null
    setAnimatingClass(false)
  }, [applyVisualState, setAnimatingClass])

  const ensureAnimationFrame = useCallback((): void => {
    if (typeof window === 'undefined') {
      return
    }
    if (animationFrameRef.current !== null) {
      return
    }
    setAnimatingClass(true)
    animationFrameRef.current = window.requestAnimationFrame(stepAnimation)
  }, [setAnimatingClass, stepAnimation])

  const resetTransform = useCallback((animated = false): void => {
    setTargetNeutral()
    markInteraction()

    if (!animated) {
      syncRenderToTarget()
      applyVisualState(renderStateRef.current)
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
        setAnimatingClass(false)
      }
      return
    }
    ensureAnimationFrame()
  }, [applyVisualState, ensureAnimationFrame, markInteraction, setAnimatingClass, setTargetNeutral, syncRenderToTarget])

  const updateDragTargetFromPointer = useCallback((pointer: PreviewPointerMetrics): void => {
    const dragState = dragStateRef.current
    const deltaCenterX = pointer.fromCenterX - dragState.pressPointer.fromCenterX
    const deltaCenterY = pointer.fromCenterY - dragState.pressPointer.fromCenterY
    dragState.targetPointer = pointer
    dragState.targetRotateX = clamp(
      dragState.startRotateX - deltaCenterY * PREVIEW_ROTATE_X_LIMIT,
      -PREVIEW_ROTATE_X_LIMIT,
      PREVIEW_ROTATE_X_LIMIT
    )
    dragState.targetRotateY = clamp(
      dragState.startRotateY + deltaCenterX * PREVIEW_ROTATE_Y_LIMIT,
      -PREVIEW_ROTATE_Y_LIMIT,
      PREVIEW_ROTATE_Y_LIMIT
    )
  }, [])

  const resolveDragPointer = useCallback((dragState: PreviewDragState, clientX: number, clientY: number): PreviewPointerMetrics => {
    if (dragState.anchorRect) {
      return resolvePointerMetricsFromRect(dragState.anchorRect, clientX, clientY)
    }
    return resolvePointerMetrics(cardRef.current, clientX, clientY)
  }, [])

  const advanceDragInteraction = useCallback((clientX: number, clientY: number): void => {
    const dragState = dragStateRef.current
    const pointer = resolveDragPointer(dragState, clientX, clientY)

    if (!dragState.moved) {
      const movedDistance = Math.hypot(clientX - dragState.pressX, clientY - dragState.pressY)
      if (movedDistance < PREVIEW_DRAG_START_DISTANCE_PX) {
        return
      }
      dragState.moved = true
    }

    updateDragTargetFromPointer(pointer)
    markInteraction()
    ensureAnimationFrame()
  }, [ensureAnimationFrame, markInteraction, resolveDragPointer, updateDragTargetFromPointer])

  const onWindowPointerMove = useCallback((event: PointerEvent): void => {
    const dragState = dragStateRef.current
    if (!dragState.dragging) {
      return
    }
    if (dragState.pointerId !== -1 && event.pointerId !== dragState.pointerId) {
      return
    }

    if (event.cancelable) {
      event.preventDefault()
    }

    advanceDragInteraction(event.clientX, event.clientY)
  }, [advanceDragInteraction])

  const onWindowPointerEnd = useCallback((event: PointerEvent): void => {
    const dragState = dragStateRef.current
    if (dragState.pointerId !== -1 && event.pointerId !== dragState.pointerId) {
      return
    }
    stopDragRef.current()
  }, [])

  const onWindowBlur = useCallback((): void => {
    stopDragRef.current()
  }, [])

  const attachWindowListeners = useCallback((): void => {
    if (windowListenersAttachedRef.current) {
      return
    }
    windowListenersAttachedRef.current = true
    window.addEventListener('pointermove', onWindowPointerMove, { passive: false })
    window.addEventListener('pointerup', onWindowPointerEnd)
    window.addEventListener('pointercancel', onWindowPointerEnd)
    window.addEventListener('blur', onWindowBlur)
  }, [onWindowBlur, onWindowPointerEnd, onWindowPointerMove])

  const detachWindowListeners = useCallback((): void => {
    if (!windowListenersAttachedRef.current) {
      return
    }
    windowListenersAttachedRef.current = false
    window.removeEventListener('pointermove', onWindowPointerMove)
    window.removeEventListener('pointerup', onWindowPointerEnd)
    window.removeEventListener('pointercancel', onWindowPointerEnd)
    window.removeEventListener('blur', onWindowBlur)
  }, [onWindowBlur, onWindowPointerEnd, onWindowPointerMove])

  const stopDrag = useCallback((withRebound = true): void => {
    const dragState = dragStateRef.current
    const wasDragging = dragState.dragging
    const pointerId = dragState.pointerId
    const captureHost = captureHostRef.current

    if (captureHost && pointerId !== -1) {
      try {
        if (captureHost.hasPointerCapture(pointerId)) {
          captureHost.releasePointerCapture(pointerId)
        }
      } catch {
        // 忽略释放失败，避免阻断关闭流程
      }
    }
    captureHostRef.current = null

    dragState.dragging = false
    dragState.pointerId = -1
    dragState.anchorRect = null
    dragState.pressX = 0
    dragState.pressY = 0
    dragState.pressPointer = clonePointer(DEFAULT_POINTER_METRICS)
    dragState.startRotateX = 0
    dragState.startRotateY = 0
    dragState.moved = false
    setDragging(false)
    detachWindowListeners()

    if (withRebound && wasDragging) {
      resetTransform(true)
      return
    }

    markInteraction()
  }, [detachWindowListeners, markInteraction, resetTransform])

  useEffect(() => {
    stopDragRef.current = stopDrag
  }, [stopDrag])

  const startDrag = useCallback((event: ReactPointerEvent<HTMLDivElement>): void => {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return
    }

    event.preventDefault()
    stopDrag(false)
    markInteraction()

    try {
      event.currentTarget.setPointerCapture(event.pointerId)
      captureHostRef.current = event.currentTarget
    } catch {
      // 捕获失败时继续，窗口级监听兜底
      captureHostRef.current = null
    }

    const dragState = dragStateRef.current
    const liveRect = cardRef.current?.getBoundingClientRect() ?? null
    dragState.anchorRect = liveRect
      ? {
          left: liveRect.left,
          top: liveRect.top,
          width: liveRect.width,
          height: liveRect.height
        }
      : null
    const pointer = resolveDragPointer(dragState, event.clientX, event.clientY)
    dragState.dragging = true
    dragState.pointerId = event.pointerId
    dragState.pressX = event.clientX
    dragState.pressY = event.clientY
    dragState.pressPointer = clonePointer(pointer)
    dragState.startRotateX = renderStateRef.current.rotateX
    dragState.startRotateY = renderStateRef.current.rotateY
    dragState.moved = false
    dragState.targetPointer = clonePointer(renderStateRef.current.pointer)

    setDragging(true)
    attachWindowListeners()
    ensureAnimationFrame()
  }, [attachWindowListeners, ensureAnimationFrame, markInteraction, resolveDragPointer, stopDrag])

  const onDragMove = useCallback((event: ReactPointerEvent<HTMLDivElement>): void => {
    const dragState = dragStateRef.current
    if (!dragState.dragging) {
      return
    }
    if (dragState.pointerId !== -1 && event.pointerId !== dragState.pointerId) {
      return
    }

    event.preventDefault()
    advanceDragInteraction(event.clientX, event.clientY)
  }, [advanceDragInteraction])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => {
      prefersReducedMotionRef.current = media.matches
      if (media.matches) {
        clearIdleTimer()
        stopIdleFloat()
        return
      }
      scheduleIdleFloat()
    }

    update()
    media.addEventListener('change', update)
    return () => {
      media.removeEventListener('change', update)
    }
  }, [clearIdleTimer, scheduleIdleFloat, stopIdleFloat])

  useEffect(() => {
    markInteraction()
    return () => {
      stopDrag(false)
      clearIdleTimer()
      stopIdleFloat()
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
      cardRef.current?.classList.remove('preview-animating')
    }
  }, [clearIdleTimer, markInteraction, stopDrag, stopIdleFloat])

  return {
    cardRef,
    shineRef,
    dragging,
    startDrag,
    onDragMove,
    stopDrag,
    resetTransform
  }
}
