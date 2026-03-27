import type { CardImageAssets } from '@/lib/card-image'

// 统一走 ptcgp-assets CDN 的其他静态资源目录
export function getCardBackImageUrl(assets: CardImageAssets): string {
  const baseUrl = assets.misc_cdn_base_url.trim()
  if (baseUrl.length === 0) {
    return ''
  }
  return `${baseUrl}/cardback.png`
}

// 卡背图加载失败时直接隐藏图片，回退到背板纯色背景
export function hideBrokenCardBackImage(image: HTMLImageElement): void {
  image.style.display = 'none'
}
