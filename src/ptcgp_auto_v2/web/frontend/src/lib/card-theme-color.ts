import { FastAverageColor } from 'fast-average-color'

import { readStorageValue, writeStorageValue } from './storage'

type CardThemeColorEngine = 'fast-average-color' | 'node-vibrant' | 'key-hash'

interface CardColorCacheEntry {
  engine: CardThemeColorEngine
  rgb: [number, number, number]
  hex: string
  updatedAt: string
}

interface CardColorCacheStorage {
  entries: Record<string, CardColorCacheEntry>
}

interface CardThemeColorResult {
  engine: CardThemeColorEngine
  rgb: [number, number, number]
  hex: string
  fromCache: boolean
}

interface ResolveCardThemeColorInput {
  cacheKey: string
  imageUrl: string
}

const COLOR_CACHE_STORAGE_KEY = 'ptcgp_card_color_cache_v2'
const COLOR_CACHE_LIMIT = 280
const THEME_COLOR_ENGINE_STORAGE_KEY = 'ptcgp_theme_color_engine_v1'
// 视觉优先：默认使用 node-vibrant，得到更明显的主色与光晕层次
const DEFAULT_THEME_COLOR_ENGINE: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'> = 'node-vibrant'
const DEFAULT_THEME_COLOR: [number, number, number] = [126, 168, 220]

const memoryColorCache = new Map<string, CardThemeColorResult>()
let colorCacheStorage: CardColorCacheStorage | null = null
let fastAverageColorInstance: FastAverageColor | null = null
let vibrantModulePromise: Promise<typeof import('node-vibrant/browser')> | null = null

function clampChannel(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }
  if (value < 0) {
    return 0
  }
  if (value > 255) {
    return 255
  }
  return Math.round(value)
}

function toHex(rgb: [number, number, number]): string {
  const [r, g, b] = rgb
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

function nowTimestamp(): string {
  return new Date().toISOString()
}

function resolveColorCacheStorage(): CardColorCacheStorage {
  if (colorCacheStorage) {
    return colorCacheStorage
  }

  const raw = readStorageValue(COLOR_CACHE_STORAGE_KEY)
  if (!raw) {
    colorCacheStorage = { entries: {} }
    return colorCacheStorage
  }

  try {
    const parsed = JSON.parse(raw) as CardColorCacheStorage
    colorCacheStorage = parsed?.entries ? parsed : { entries: {} }
  } catch {
    colorCacheStorage = { entries: {} }
  }

  return colorCacheStorage
}

function persistColorCacheStorage(): void {
  writeStorageValue(COLOR_CACHE_STORAGE_KEY, JSON.stringify(resolveColorCacheStorage()))
}

function trimColorCacheIfNeeded(): void {
  const storage = resolveColorCacheStorage()
  const entries = Object.entries(storage.entries)
  if (entries.length <= COLOR_CACHE_LIMIT) {
    return
  }

  entries
    .sort(([, a], [, b]) => a.updatedAt.localeCompare(b.updatedAt))
    .slice(0, entries.length - COLOR_CACHE_LIMIT)
    .forEach(([key]) => {
      delete storage.entries[key]
    })
}

function getColorFromStorage(cacheKey: string): CardThemeColorResult | null {
  const entry = resolveColorCacheStorage().entries[cacheKey]
  if (!entry) {
    return null
  }
  return {
    engine: entry.engine,
    rgb: entry.rgb,
    hex: entry.hex,
    fromCache: true
  }
}

function setColorToStorage(cacheKey: string, result: CardThemeColorResult): void {
  const storage = resolveColorCacheStorage()
  storage.entries[cacheKey] = {
    engine: result.engine,
    rgb: result.rgb,
    hex: result.hex,
    updatedAt: nowTimestamp()
  }
  trimColorCacheIfNeeded()
  persistColorCacheStorage()
}

function deriveColorFromKey(cacheKey: string): [number, number, number] {
  if (cacheKey.trim().length === 0) {
    return DEFAULT_THEME_COLOR
  }

  let hash = 2166136261
  for (let index = 0; index < cacheKey.length; index += 1) {
    hash ^= cacheKey.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }

  const r = 84 + (hash & 0x7f)
  const g = 84 + ((hash >>> 8) & 0x7f)
  const b = 84 + ((hash >>> 16) & 0x7f)

  return [clampChannel(r), clampChannel(g), clampChannel(b)]
}

function resolvePreferredEngine(): Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'> {
  const raw = readStorageValue(THEME_COLOR_ENGINE_STORAGE_KEY)
  if (raw === 'fast-average-color' || raw === 'node-vibrant') {
    return raw
  }
  return DEFAULT_THEME_COLOR_ENGINE
}

function persistPreferredEngine(engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>): void {
  writeStorageValue(THEME_COLOR_ENGINE_STORAGE_KEY, engine)
}

function getFastAverageColorInstance(): FastAverageColor {
  if (!fastAverageColorInstance) {
    fastAverageColorInstance = new FastAverageColor()
  }
  return fastAverageColorInstance
}

async function extractByFastAverageColor(imageUrl: string): Promise<[number, number, number] | null> {
  if (imageUrl.trim().length === 0) {
    return null
  }
  try {
    const fac = getFastAverageColorInstance()
    const color = await fac.getColorAsync(imageUrl, {
      crossOrigin: 'anonymous'
    })
    return [clampChannel(color.value[0]), clampChannel(color.value[1]), clampChannel(color.value[2])]
  } catch {
    return null
  }
}

async function extractByNodeVibrant(imageUrl: string): Promise<[number, number, number] | null> {
  if (imageUrl.trim().length === 0) {
    return null
  }
  try {
    vibrantModulePromise ??= import('node-vibrant/browser')
    const { Vibrant } = await vibrantModulePromise
    const palette = await Vibrant.from(imageUrl).getPalette()
    const swatch = palette.Vibrant
      ?? palette.LightVibrant
      ?? palette.Muted
      ?? palette.DarkVibrant
      ?? palette.LightMuted
      ?? palette.DarkMuted
      ?? null
    if (!swatch) {
      return null
    }
    return [clampChannel(swatch.rgb[0]), clampChannel(swatch.rgb[1]), clampChannel(swatch.rgb[2])]
  } catch {
    return null
  }
}

async function extractColorByEngine(
  engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>,
  imageUrl: string
): Promise<[number, number, number] | null> {
  if (engine === 'fast-average-color') {
    return extractByFastAverageColor(imageUrl)
  }
  return extractByNodeVibrant(imageUrl)
}


export function getDefaultThemeRgb(): [number, number, number] {
  return DEFAULT_THEME_COLOR
}

export async function resolveCardThemeColor(input: ResolveCardThemeColorInput): Promise<CardThemeColorResult> {
  const memory = memoryColorCache.get(input.cacheKey)
  if (memory) {
    return { ...memory, fromCache: true }
  }

  const stored = getColorFromStorage(input.cacheKey)
  if (stored) {
    memoryColorCache.set(input.cacheKey, { ...stored, fromCache: false })
    return stored
  }

  const preferredEngine = resolvePreferredEngine()
  let rgb = await extractColorByEngine(preferredEngine, input.imageUrl)
  let resolvedEngine: CardThemeColorEngine = preferredEngine

  if (!rgb) {
    const backupEngine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'> = preferredEngine === 'fast-average-color'
      ? 'node-vibrant'
      : 'fast-average-color'
    rgb = await extractColorByEngine(backupEngine, input.imageUrl)
    if (rgb) {
      resolvedEngine = backupEngine
      persistPreferredEngine(backupEngine)
    }
  }

  if (!rgb) {
    resolvedEngine = 'key-hash'
    rgb = deriveColorFromKey(input.cacheKey)
  }

  const result: CardThemeColorResult = {
    engine: resolvedEngine,
    rgb,
    hex: toHex(rgb),
    fromCache: false
  }
  memoryColorCache.set(input.cacheKey, result)
  setColorToStorage(input.cacheKey, result)
  return result
}
