export type CardPreviewEffectId = 'standard' | 'holo' | 'prismatic'

interface CardPreviewLayerRule {
  opacity: number
  blend: string
  gradient: string
}

export interface CardPreviewEffectRule {
  id: CardPreviewEffectId
  borderGlowBoost: number
  foil: CardPreviewLayerRule
  glare: CardPreviewLayerRule
  spark: CardPreviewLayerRule
  // 允许插件追加自定义变量，便于扩展光效层
  buildVars?: (input: CardPreviewVisualInput, rgb: [number, number, number]) => Record<string, string>
}

// 主题色提取失败时的兜底色
const DEFAULT_THEME_RGB: [number, number, number] = [126, 168, 220]
// 光效注册表：允许按稀有度映射到不同分层参数
const EFFECT_REGISTRY = new Map<CardPreviewEffectId, CardPreviewEffectRule>()

function createDefaultEffects(): CardPreviewEffectRule[] {
  return [
    {
      id: 'standard',
      borderGlowBoost: 0.92,
      foil: {
        opacity: 0.26,
        blend: 'soft-light',
        gradient: 'linear-gradient(130deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 42%, rgba(255,255,255,0.14) 76%, rgba(255,255,255,0.02) 100%)'
      },
      glare: {
        opacity: 0.56,
        blend: 'screen',
        gradient: 'radial-gradient(circle at var(--preview-glare-x, 50%) var(--preview-glare-y, 50%), rgba(255,255,255,0.66) 0%, rgba(255,255,255,0.22) 28%, rgba(255,255,255,0) 62%)'
      },
      spark: {
        opacity: 0.2,
        blend: 'overlay',
        gradient: 'repeating-linear-gradient(115deg, rgba(255,255,255,0.18) 0, rgba(255,255,255,0.18) 2px, rgba(255,255,255,0) 2px, rgba(255,255,255,0) 12px)'
      }
    },
    {
      id: 'holo',
      borderGlowBoost: 1.2,
      foil: {
        opacity: 0.4,
        blend: 'color-dodge',
        gradient: 'linear-gradient(118deg, rgba(255,86,124,0.4) 0%, rgba(88,195,255,0.46) 28%, rgba(123,255,187,0.34) 54%, rgba(255,222,125,0.36) 100%)'
      },
      glare: {
        opacity: 0.66,
        blend: 'screen',
        gradient: 'radial-gradient(circle at var(--preview-glare-x, 50%) var(--preview-glare-y, 50%), rgba(255,255,255,0.86) 0%, rgba(255,255,255,0.24) 24%, rgba(255,255,255,0) 64%)'
      },
      spark: {
        opacity: 0.32,
        blend: 'hard-light',
        gradient: 'repeating-linear-gradient(130deg, rgba(255,255,255,0.3) 0, rgba(255,255,255,0.3) 1.5px, rgba(255,255,255,0) 1.5px, rgba(255,255,255,0) 10px)'
      }
    },
    {
      id: 'prismatic',
      borderGlowBoost: 1.42,
      foil: {
        opacity: 0.48,
        blend: 'color-dodge',
        gradient: 'linear-gradient(112deg, rgba(255,64,164,0.46) 0%, rgba(96,136,255,0.52) 24%, rgba(64,245,255,0.44) 48%, rgba(140,255,184,0.38) 68%, rgba(255,204,92,0.46) 100%)'
      },
      glare: {
        opacity: 0.74,
        blend: 'screen',
        gradient: 'radial-gradient(circle at var(--preview-glare-x, 50%) var(--preview-glare-y, 50%), rgba(255,255,255,0.92) 0%, rgba(255,255,255,0.32) 26%, rgba(255,255,255,0) 62%)'
      },
      spark: {
        opacity: 0.38,
        blend: 'hard-light',
        gradient: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.38) 0, rgba(255,255,255,0.38) 1px, rgba(255,255,255,0) 1px, rgba(255,255,255,0) 8px)'
      }
    }
  ]
}

function clampChannel(value: number): number {
  if (value < 0) {
    return 0
  }
  if (value > 255) {
    return 255
  }
  return Math.round(value)
}

function clampOpacity(value: number): number {
  if (value < 0) {
    return 0
  }
  if (value > 1) {
    return 1
  }
  return value
}

function resolveEffectByRarity(rarity: string): CardPreviewEffectId {
  const token = rarity.trim().toUpperCase()
  if (/(CROWN|IMMERSIVE|SAR|UR|HR)/.test(token) || /[★☆✶]{3,}/.test(token)) {
    return 'prismatic'
  }
  if (/(EX|RR|SR|AR|PROMO)/.test(token) || /[★☆✶]{2}/.test(token)) {
    return 'holo'
  }
  return 'standard'
}

function rgba(rgb: [number, number, number], alpha: number): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${clampOpacity(alpha).toFixed(3)})`
}

export interface CardPreviewVisualInput {
  rarity: string
  rgb?: [number, number, number] | null
  effectId?: CardPreviewEffectId
}

export function registerCardPreviewEffect(rule: CardPreviewEffectRule): void {
  EFFECT_REGISTRY.set(rule.id, rule)
}

export function listCardPreviewEffects(): CardPreviewEffectRule[] {
  return Array.from(EFFECT_REGISTRY.values())
}

export function resolveCardPreviewEffectId(rarity: string): CardPreviewEffectId {
  return resolveEffectByRarity(rarity)
}

export function resolveCardPreviewEffectRule(effectId: CardPreviewEffectId): CardPreviewEffectRule {
  return EFFECT_REGISTRY.get(effectId) ?? EFFECT_REGISTRY.get('standard')!
}

export function buildCardPreviewVisualVars(input: CardPreviewVisualInput): Record<string, string> {
  // 按稀有度和主题色输出 CSS 变量，驱动统一预览层效果
  const effectId = input.effectId ?? resolveCardPreviewEffectId(input.rarity)
  const effect = resolveCardPreviewEffectRule(effectId)
  const rawRgb = input.rgb ?? DEFAULT_THEME_RGB
  const rgb: [number, number, number] = [
    clampChannel(rawRgb[0]),
    clampChannel(rawRgb[1]),
    clampChannel(rawRgb[2])
  ]

  const glowBoost = effect.borderGlowBoost

  const baseVars: Record<string, string> = {
    '--preview-theme-rgb': `${rgb[0]}, ${rgb[1]}, ${rgb[2]}`,
    '--preview-theme-soft': rgba(rgb, 0.22 * glowBoost),
    '--preview-theme-strong': rgba(rgb, 0.45 * glowBoost),
    '--preview-foil-opacity': effect.foil.opacity.toFixed(3),
    '--preview-foil-gradient': effect.foil.gradient,
    '--preview-foil-blend': effect.foil.blend,
    '--preview-glare-opacity': effect.glare.opacity.toFixed(3),
    '--preview-glare-gradient': effect.glare.gradient,
    '--preview-glare-blend': effect.glare.blend,
    '--preview-spark-opacity': effect.spark.opacity.toFixed(3),
    '--preview-spark-gradient': effect.spark.gradient,
    '--preview-spark-blend': effect.spark.blend,
    '--preview-border-glow': rgba(rgb, 0.5 * glowBoost),
    '--preview-border-line': rgba(rgb, 0.66 * glowBoost)
  }

  if (!effect.buildVars) {
    return baseVars
  }

  return {
    ...baseVars,
    ...effect.buildVars(input, rgb)
  }
}

for (const effect of createDefaultEffects()) {
  registerCardPreviewEffect(effect)
}
