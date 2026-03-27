interface PlayCardFlipEntranceOptions {
  from?: HTMLElement | null
  fromRect?: PreviewRectLike | null
  to: HTMLElement
  rotateTarget?: HTMLElement | null
  durationMs?: number
}

interface PlayCardFlipExitGhostOptions {
  from: HTMLElement
  fromRect?: PreviewRectLike | null
  to?: HTMLElement | null
  toRect?: PreviewRectLike | null
  durationMs?: number
}

export interface PreviewRectLike {
  // 使用页面绝对坐标，避免打开后页面滚动导致回飞目标错位
  left: number
  top: number
  width: number
  height: number
}

interface ViewportRectLike {
  left: number
  top: number
  width: number
  height: number
}

interface PathVars {
  tx: number
  ty: number
  sx: number
  sy: number
}

interface EntranceAnimations {
  path: Animation
  rotate: Animation
}

// 统一按标准卡牌比例裁切动画矩形，避免进退场过程中出现非等比拉伸
const CARD_FRAME_RATIO = 2 / 3
const DEFAULT_FLIP_DURATION = 1650
const DEFAULT_ROTATE_DURATION = 980
const ENTRANCE_TOTAL_ROTATE_DEG = -360
const EXIT_TOTAL_ROTATE_DEG = 360
const ENTRANCE_KEYFRAME_STEPS = 36
const ACTIVE_ENTRANCE_ANIMATIONS = new WeakMap<HTMLElement, EntranceAnimations>()
const ACTIVE_EXIT_GHOSTS = new Set<HTMLElement>()

export function snapshotElementRect(element: HTMLElement | null | undefined): PreviewRectLike | null {
  if (!element) {
    return null
  }
  const rect = element.getBoundingClientRect()
  if (!isValidRect(rect)) {
    return null
  }
  const normalized = normalizeCardRect(rect)
  return {
    left: normalized.left + window.scrollX,
    top: normalized.top + window.scrollY,
    width: normalized.width,
    height: normalized.height
  }
}

function isValidRect(rect: PreviewRectLike): boolean {
  return rect.width > 0 && rect.height > 0
}

function clamp01(value: number): number {
  if (value < 0) {
    return 0
  }
  if (value > 1) {
    return 1
  }
  return value
}

function lerp(from: number, to: number, progress: number): number {
  return from + (to - from) * progress
}

function nextAnimationFrame(): Promise<void> {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

function easeOutCubic(value: number): number {
  const t = clamp01(value)
  const inv = 1 - t
  return 1 - inv * inv * inv
}

function buildPathTransform(vars: PathVars): string {
  return (
    `translate3d(${vars.tx.toFixed(3)}px, ${vars.ty.toFixed(3)}px, 0) ` +
    `scale(${vars.sx.toFixed(5)}, ${vars.sy.toFixed(5)})`
  )
}

function normalizeCardRect<T extends ViewportRectLike>(rect: T): ViewportRectLike {
  const currentRatio = rect.width / rect.height
  if (Math.abs(currentRatio - CARD_FRAME_RATIO) <= 0.0001) {
    return {
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height
    }
  }

  if (currentRatio > CARD_FRAME_RATIO) {
    const width = rect.height * CARD_FRAME_RATIO
    const left = rect.left + (rect.width - width) / 2
    return {
      left,
      top: rect.top,
      width,
      height: rect.height
    }
  }

  const height = rect.width / CARD_FRAME_RATIO
  const top = rect.top + (rect.height - height) / 2
  return {
    left: rect.left,
    top,
    width: rect.width,
    height
  }
}

function resolveViewportRect(rect: PreviewRectLike): ViewportRectLike {
  return normalizeCardRect({
    left: rect.left - window.scrollX,
    top: rect.top - window.scrollY,
    width: rect.width,
    height: rect.height
  })
}

function resolvePathVars(from: ViewportRectLike | null, to: ViewportRectLike): PathVars {
  let tx = 0
  let ty = 0
  let sx = 1
  let sy = 1

  if (from && isValidRect(from)) {
    tx = from.left - to.left
    ty = from.top - to.top
    sx = from.width / to.width
    sy = from.height / to.height
  }

  return { tx, ty, sx, sy }
}

function buildPathKeyframes(from: PathVars, to: PathVars): Keyframe[] {
  const keyframes: Keyframe[] = []
  for (let step = 0; step <= ENTRANCE_KEYFRAME_STEPS; step += 1) {
    const offset = step / ENTRANCE_KEYFRAME_STEPS
    const eased = easeOutCubic(offset)
    keyframes.push({
      offset,
      transform: buildPathTransform({
        tx: lerp(from.tx, to.tx, eased),
        ty: lerp(from.ty, to.ty, eased),
        sx: lerp(from.sx, to.sx, eased),
        sy: lerp(from.sy, to.sy, eased)
      })
    })
  }
  return keyframes
}

function buildRotateKeyframes(fromDeg: number, toDeg: number): Keyframe[] {
  const keyframes: Keyframe[] = []
  for (let step = 0; step <= ENTRANCE_KEYFRAME_STEPS; step += 1) {
    const progress = step / ENTRANCE_KEYFRAME_STEPS
    keyframes.push({
      offset: progress,
      transform: `rotateY(${lerp(fromDeg, toDeg, progress).toFixed(3)}deg)`
    })
  }
  return keyframes
}

function resolveLiveViewportRect(
  element: HTMLElement | null | undefined,
  fallbackRect: PreviewRectLike | null | undefined
): ViewportRectLike | null {
  if (element && element.isConnected) {
    const rect = normalizeCardRect(element.getBoundingClientRect())
    if (isValidRect(rect)) {
      return rect
    }
  }
  if (fallbackRect && isValidRect(fallbackRect)) {
    return resolveViewportRect(fallbackRect)
  }
  return null
}

function clearTrackedAnimations(target: HTMLElement, rotateTarget: HTMLElement): void {
  const tracked = ACTIVE_ENTRANCE_ANIMATIONS.get(target)
  if (tracked) {
    tracked.path.cancel()
    tracked.rotate.cancel()
    ACTIVE_ENTRANCE_ANIMATIONS.delete(target)
  }
  target.style.removeProperty('will-change')
  target.style.removeProperty('transform-origin')
  target.style.removeProperty('transform')
  rotateTarget.style.removeProperty('will-change')
  rotateTarget.style.removeProperty('transform-origin')
  rotateTarget.style.removeProperty('transform')
}

export function clearCardFlipExitGhosts(): void {
  for (const ghost of ACTIVE_EXIT_GHOSTS) {
    ghost.remove()
  }
  ACTIVE_EXIT_GHOSTS.clear()
}

export async function playCardFlipEntrance(options: PlayCardFlipEntranceOptions): Promise<void> {
  const pathTarget = options.to
  const rotateTarget = options.rotateTarget ?? pathTarget
  const origin = options.from ?? null
  const pathDurationMs = options.durationMs ?? DEFAULT_FLIP_DURATION
  const rotateDurationMs = Math.min(pathDurationMs, DEFAULT_ROTATE_DURATION)

  clearTrackedAnimations(pathTarget, rotateTarget)

  if (!pathTarget.isConnected || !rotateTarget.isConnected) {
    return
  }

  const targetRect = normalizeCardRect(pathTarget.getBoundingClientRect())
  if (!isValidRect(targetRect)) {
    return
  }

  let originRect: ViewportRectLike | null = null
  if (options.fromRect && isValidRect(options.fromRect)) {
    originRect = resolveViewportRect(options.fromRect)
  } else if (origin && origin.isConnected) {
      const liveRect = normalizeCardRect(origin.getBoundingClientRect())
    if (isValidRect(liveRect)) {
      originRect = liveRect
    }
  }

  const pathStart = resolvePathVars(originRect, targetRect)
  const pathKeyframes = buildPathKeyframes(pathStart, { tx: 0, ty: 0, sx: 1, sy: 1 })
  const rotateKeyframes = buildRotateKeyframes(ENTRANCE_TOTAL_ROTATE_DEG, 0)

  pathTarget.style.setProperty('transform-origin', 'top left')
  pathTarget.style.setProperty('will-change', 'transform')
  pathTarget.style.setProperty('transform', buildPathTransform(pathStart))

  rotateTarget.style.setProperty('transform-origin', 'center center')
  rotateTarget.style.setProperty('will-change', 'transform')
  rotateTarget.style.setProperty('transform', `rotateY(${ENTRANCE_TOTAL_ROTATE_DEG.toFixed(3)}deg)`)

  const pathAnimation = pathTarget.animate(pathKeyframes, {
    duration: pathDurationMs,
    easing: 'linear',
    fill: 'forwards'
  })
  const rotateAnimation = rotateTarget.animate(rotateKeyframes, {
    duration: rotateDurationMs,
    easing: 'linear',
    fill: 'forwards'
  })
  const trackedAnimations: EntranceAnimations = {
    path: pathAnimation,
    rotate: rotateAnimation
  }
  ACTIVE_ENTRANCE_ANIMATIONS.set(pathTarget, trackedAnimations)

  await Promise.allSettled([pathAnimation.finished, rotateAnimation.finished])

  const tracked = ACTIVE_ENTRANCE_ANIMATIONS.get(pathTarget)
  if (!tracked || tracked.path !== pathAnimation || tracked.rotate !== rotateAnimation) {
    return
  }

  // 先让浏览器真正绘制到最终帧，再释放控制权，避免最后一拍出现明显顿挫
  await nextAnimationFrame()
  const latestTracked = ACTIVE_ENTRANCE_ANIMATIONS.get(pathTarget)
  if (!latestTracked || latestTracked.path !== pathAnimation || latestTracked.rotate !== rotateAnimation) {
    return
  }

  // 关键：入口动画结束后必须释放 transform 控制权，否则会压住拖拽旋转
  pathAnimation.cancel()
  rotateAnimation.cancel()
  ACTIVE_ENTRANCE_ANIMATIONS.delete(pathTarget)
  pathTarget.style.removeProperty('will-change')
  pathTarget.style.removeProperty('transform-origin')
  pathTarget.style.removeProperty('transform')
  rotateTarget.style.removeProperty('will-change')
  rotateTarget.style.removeProperty('transform-origin')
  rotateTarget.style.removeProperty('transform')
}

export async function playCardFlipExitGhost(options: PlayCardFlipExitGhostOptions): Promise<void> {
  const source = options.from
  const sourceRectOverride = options.fromRect ?? null
  const destination = options.to ?? null
  const destinationRect = options.toRect ?? null
  const pathDurationMs = options.durationMs ?? DEFAULT_FLIP_DURATION
  const rotateDurationMs = Math.min(pathDurationMs, DEFAULT_FLIP_DURATION)

  if (!source.isConnected) {
    return
  }

  const sourceRect = sourceRectOverride && isValidRect(sourceRectOverride)
    ? resolveViewportRect(sourceRectOverride)
    : normalizeCardRect(source.getBoundingClientRect())
  if (!isValidRect(sourceRect)) {
    return
  }

  const initialTargetRect = resolveLiveViewportRect(destination, destinationRect)
  if (!initialTargetRect) {
    return
  }

  const wrapper = document.createElement('div')
  wrapper.className = 'card-preview-exit-ghost'
  wrapper.style.position = 'fixed'
  wrapper.style.left = `${sourceRect.left}px`
  wrapper.style.top = `${sourceRect.top}px`
  wrapper.style.width = `${sourceRect.width}px`
  wrapper.style.height = `${sourceRect.height}px`
  wrapper.style.pointerEvents = 'none'
  wrapper.style.zIndex = '2000'
  wrapper.style.perspective = '1450px'
  wrapper.style.transformOrigin = 'top left'
  wrapper.style.transformStyle = 'preserve-3d'
  wrapper.style.willChange = 'transform'

  const clone = source.cloneNode(true)
  if (!(clone instanceof HTMLElement)) {
    return
  }
  const rotateWrapper = document.createElement('div')
  rotateWrapper.className = 'card-preview-exit-ghost-rotator'
  rotateWrapper.style.width = '100%'
  rotateWrapper.style.height = '100%'
  rotateWrapper.style.transformOrigin = 'center center'
  rotateWrapper.style.transformStyle = 'preserve-3d'
  rotateWrapper.style.willChange = 'transform'

  clone.style.width = '100%'
  clone.style.height = '100%'
  clone.style.transformOrigin = 'center center'
  clone.style.willChange = 'transform'
  rotateWrapper.appendChild(clone)
  wrapper.appendChild(rotateWrapper)
  document.body.appendChild(wrapper)
  ACTIVE_EXIT_GHOSTS.add(wrapper)

  await new Promise<void>((resolve) => {
    const startTime = performance.now()

    const step = (now: number) => {
      const elapsed = now - startTime
      const pathProgress = clamp01(elapsed / pathDurationMs)
      const easedPath = easeOutCubic(pathProgress)
      const targetRect = resolveLiveViewportRect(destination, destinationRect) ?? initialTargetRect
      const pathVars = resolvePathVars(targetRect, sourceRect)

      wrapper.style.transform = buildPathTransform({
        tx: lerp(0, pathVars.tx, easedPath),
        ty: lerp(0, pathVars.ty, easedPath),
        sx: lerp(1, pathVars.sx, easedPath),
        sy: lerp(1, pathVars.sy, easedPath)
      })
      const rotateProgress = clamp01(elapsed / rotateDurationMs)
      const easedRotate = easeOutCubic(rotateProgress)
      rotateWrapper.style.transform = `rotateY(${lerp(0, EXIT_TOTAL_ROTATE_DEG, easedRotate).toFixed(3)}deg)`

      if (pathProgress < 1) {
        window.requestAnimationFrame(step)
        return
      }

      ACTIVE_EXIT_GHOSTS.delete(wrapper)
      wrapper.remove()
      resolve()
    }

    window.requestAnimationFrame(step)
  })
}
