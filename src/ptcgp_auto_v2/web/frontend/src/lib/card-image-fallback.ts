const DATASET_FALLBACK_INDEX_KEY = 'fallbackIndex'

interface CardImageFallbackUrls {
  png: string
  webp: string
  cdnPng: string
  cdnWebp: string
}

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

/**
 * 列表/网格中的卡图降级顺序：webp 代理 -> png CDN -> webp CDN。
 */
export function applyCardListImageFallback(image: HTMLImageElement, urls: CardImageFallbackUrls): void {
  applyImageFallback(image, [urls.webp, urls.cdnPng, urls.cdnWebp])
}

/**
 * 预览大图降级顺序：webp 代理 -> webp CDN -> png 代理。
 */
export function applyCardPreviewImageFallback(image: HTMLImageElement, urls: CardImageFallbackUrls): void {
  applyImageFallback(image, [urls.webp, urls.cdnWebp, urls.png])
}
