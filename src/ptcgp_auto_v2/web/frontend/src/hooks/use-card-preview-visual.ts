import { type CSSProperties, useEffect, useMemo, useState } from 'react'

import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { getCardBackImageUrl } from '@/lib/card-preview-assets'
import { buildCardPreviewVisualVars, resolveCardPreviewEffectId, type CardPreviewEffectId } from '@/lib/card-preview-effects'
import { getDefaultThemeRgb, resolveCardThemeColor } from '@/lib/card-theme-color'

type CardPreviewImageUrls = ReturnType<typeof getCardImageUrls>

interface UseCardPreviewVisualInput {
  assets: CardImageAssets
  enabled: boolean
  setCode: string
  cardNumber: number
  rarity: string
  cacheKey: string
}

interface UseCardPreviewVisualResult {
  imageUrls: CardPreviewImageUrls | null
  cardBackImageUrl: string
  effectId: CardPreviewEffectId
  visualStyle: CSSProperties
}

export function useCardPreviewVisual(input: UseCardPreviewVisualInput): UseCardPreviewVisualResult {
  const [themeRgb, setThemeRgb] = useState<[number, number, number]>(getDefaultThemeRgb)

  const imageUrls = useMemo(() => {
    if (!input.enabled) {
      return null
    }
    return getCardImageUrls(input.assets, {
      setCode: input.setCode,
      cardNumber: input.cardNumber
    })
  }, [input.assets, input.cardNumber, input.enabled, input.setCode])

  const previewImageUrl = imageUrls?.png ?? ''

  useEffect(() => {
    if (!input.enabled || input.cacheKey.length === 0 || previewImageUrl.length === 0) {
      setThemeRgb(getDefaultThemeRgb())
      return
    }
    let cancelled = false
    void resolveCardThemeColor({
      cacheKey: input.cacheKey,
      imageUrl: previewImageUrl
    }).then((result) => {
      if (!cancelled) {
        setThemeRgb(result.rgb)
      }
    }).catch(() => {
      if (!cancelled) {
        setThemeRgb(getDefaultThemeRgb())
      }
    })
    return () => {
      cancelled = true
    }
  }, [input.cacheKey, input.enabled, previewImageUrl])

  const effectId = useMemo(
    () => resolveCardPreviewEffectId(input.rarity),
    [input.rarity]
  )

  const visualStyle = useMemo(
    () =>
      buildCardPreviewVisualVars({
        rarity: input.rarity,
        rgb: themeRgb,
        effectId
      }) as CSSProperties,
    [effectId, input.rarity, themeRgb]
  )

  const cardBackImageUrl = useMemo(
    () => getCardBackImageUrl(input.assets),
    [input.assets]
  )

  return {
    imageUrls,
    cardBackImageUrl,
    effectId,
    visualStyle
  }
}
