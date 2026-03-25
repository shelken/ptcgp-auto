const DATASET_FALLBACK_INDEX_KEY = 'fallbackIndex'

/**
 * 统一图片降级策略：按顺序依次尝试备用地址。
 */
export function applyImageFallback(image: HTMLImageElement, fallbacks: readonly string[]): void {
  const currentIndexRaw = image.dataset[DATASET_FALLBACK_INDEX_KEY] ?? '0'
  const currentIndex = Number(currentIndexRaw)
  if (!Number.isFinite(currentIndex) || currentIndex < 0 || currentIndex >= fallbacks.length) {
    return
  }
  image.src = fallbacks[currentIndex]
  image.dataset[DATASET_FALLBACK_INDEX_KEY] = String(currentIndex + 1)
}
