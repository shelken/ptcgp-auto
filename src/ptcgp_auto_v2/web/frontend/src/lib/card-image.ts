const EMPTY_IMAGE_DATA_URL = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='

export interface CardImageAssets {
  card_proxy_base_url: string
  card_cdn_base_url: string
  misc_cdn_base_url: string
}

interface CardImagePayload {
  setCode?: string | null
  cardNumber?: number | null
}

export function getCardImageUrls(
  assets: CardImageAssets,
  payload: CardImagePayload,
  width: number = 400
): { png: string; webp: string; cdnPng: string; cdnWebp: string } {
  const setCode = (payload.setCode ?? '').trim()
  const cardNumber = Number(payload.cardNumber ?? 0)
  if (!setCode || !Number.isFinite(cardNumber) || cardNumber <= 0) {
    return {
      png: EMPTY_IMAGE_DATA_URL,
      webp: EMPTY_IMAGE_DATA_URL,
      cdnPng: EMPTY_IMAGE_DATA_URL,
      cdnWebp: EMPTY_IMAGE_DATA_URL
    }
  }
  return {
    png: `${assets.card_proxy_base_url}/${setCode}/${cardNumber}.png&w=${width}&output=png`,
    webp: `${assets.card_proxy_base_url}/${setCode}/${cardNumber}.webp&w=${width}&output=webp`,
    cdnPng: `${assets.card_cdn_base_url}/${setCode}/${cardNumber}.png`,
    cdnWebp: `${assets.card_cdn_base_url}/${setCode}/${cardNumber}.webp`
  }
}
