interface PlayCardFlipEntranceOptions {
  from?: HTMLElement | null
  to: HTMLElement
  durationMs?: number
}

const DEFAULT_FLIP_DURATION = 560
const DEFAULT_ENTRY_ROTATE_Y = -64
const DEFAULT_ENTRY_ROTATE_X = 9
const ORIGIN_ENTRY_ROTATE_Y = -78
const ORIGIN_ENTRY_ROTATE_X = 12
const ACTIVE_ENTRANCE_ANIMATIONS = new WeakMap<HTMLElement, Animation>()

function nextFrame(): Promise<void> {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => resolve())
    })
  })
}

function isValidRect(rect: DOMRect): boolean {
  return rect.width > 0 && rect.height > 0
}

interface EntranceFrameVars {
  translateX: number
  translateY: number
  scaleX: number
  scaleY: number
  rotateY: number
  rotateX: number
}

function resolveEntryFrameVars(from: DOMRect | null, to: DOMRect): EntranceFrameVars {
  let translateX = 0
  let translateY = 18
  let scaleX = 0.94
  let scaleY = 0.94
  let rotateY = DEFAULT_ENTRY_ROTATE_Y
  let rotateX = DEFAULT_ENTRY_ROTATE_X

  if (from && isValidRect(from)) {
    translateX = from.left - to.left
    translateY = from.top - to.top
    scaleX = from.width / to.width
    scaleY = from.height / to.height
    rotateY = ORIGIN_ENTRY_ROTATE_Y
    rotateX = ORIGIN_ENTRY_ROTATE_X
  }

  return {
    translateX,
    translateY,
    scaleX,
    scaleY,
    rotateY,
    rotateX
  }
}

function resolveEntryFrames(vars: EntranceFrameVars): Keyframe[] {
  const settleRatio = 0.42
  const settleScaleX = 1 + (vars.scaleX - 1) * settleRatio
  const settleScaleY = 1 + (vars.scaleY - 1) * settleRatio

  return [
    {
      opacity: '0.92',
      transform:
        `perspective(1200px) ` +
        `translate3d(${vars.translateX.toFixed(3)}px, ${vars.translateY.toFixed(3)}px, 0) ` +
        `scale(${vars.scaleX.toFixed(5)}, ${vars.scaleY.toFixed(5)}) ` +
        `rotateY(${vars.rotateY.toFixed(3)}deg) ` +
        `rotateX(${vars.rotateX.toFixed(3)}deg)`
    },
    {
      offset: 0.65,
      opacity: '0.985',
      transform:
        `perspective(1200px) ` +
        `translate3d(${(vars.translateX * settleRatio).toFixed(3)}px, ${(vars.translateY * settleRatio).toFixed(3)}px, 0) ` +
        `scale(${settleScaleX.toFixed(5)}, ${settleScaleY.toFixed(5)}) ` +
        `rotateY(${(vars.rotateY * 0.35).toFixed(3)}deg) ` +
        `rotateX(${(vars.rotateX * 0.28).toFixed(3)}deg)`
    },
    {
      opacity: '1',
      transform: 'perspective(1200px) translate3d(0, 0, 0) scale(1, 1) rotateY(0deg) rotateX(0deg)'
    }
  ]
}

function clearActiveEntranceAnimation(target: HTMLElement): void {
  const currentAnimation = ACTIVE_ENTRANCE_ANIMATIONS.get(target)
  if (!currentAnimation) {
    return
  }
  currentAnimation.cancel()
  ACTIVE_ENTRANCE_ANIMATIONS.delete(target)
  target.style.removeProperty('will-change')
}

export async function playCardFlipEntrance(options: PlayCardFlipEntranceOptions): Promise<void> {
  const target = options.to
  const origin = options.from ?? null
  const durationMs = options.durationMs ?? DEFAULT_FLIP_DURATION

  await nextFrame()

  if (!target.isConnected) {
    return
  }

  const targetRect = target.getBoundingClientRect()
  if (!isValidRect(targetRect)) {
    return
  }

  const originRect = origin && origin.isConnected ? origin.getBoundingClientRect() : null
  const frameVars = resolveEntryFrameVars(originRect, targetRect)
  const frames = resolveEntryFrames(frameVars)

  clearActiveEntranceAnimation(target)
  target.style.setProperty('will-change', 'transform, opacity')

  const animation = target.animate(frames, {
    duration: durationMs,
    easing: 'cubic-bezier(0.2, 0.84, 0.18, 1)',
    fill: 'both'
  })

  ACTIVE_ENTRANCE_ANIMATIONS.set(target, animation)

  try {
    await animation.finished
  } catch {
    return
  }

  if (ACTIVE_ENTRANCE_ANIMATIONS.get(target) !== animation) {
    return
  }

  ACTIVE_ENTRANCE_ANIMATIONS.delete(target)
  target.style.removeProperty('will-change')
  animation.cancel()
}
