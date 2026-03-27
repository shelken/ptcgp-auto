import { FastAverageColor } from 'fast-average-color'

export type CardThemeColorEngine = 'fast-average-color' | 'node-vibrant' | 'key-hash'

interface CardColorCacheEntry {
  engine: CardThemeColorEngine
  rgb: [number, number, number]
  hex: string
  updatedAt: string
}

interface CardColorCacheStorage {
  entries: Record<string, CardColorCacheEntry>
}

export interface CardThemeColorResult {
  engine: CardThemeColorEngine
  rgb: [number, number, number]
  hex: string
  fromCache: boolean
}

interface ResolveCardThemeColorInput {
  cacheKey: string
  imageUrl: string
}

interface EngineBenchmarkAggregate {
  engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>
  sampleCount: number
  successCount: number
  successRate: number
  p50Ms: number
  p95Ms: number
  bundleSizeKb: number
}

export interface CardThemeColorBenchmarkReport {
  sampleCount: number
  stats: EngineBenchmarkAggregate[]
  recommendedEngine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>
  reason: string
}

interface EngineRunPoint {
  elapsedMs: number
  success: boolean
}

const COLOR_CACHE_STORAGE_KEY = 'ptcgp_card_color_cache_v2'
const COLOR_CACHE_LIMIT = 280
const THEME_COLOR_ENGINE_STORAGE_KEY = 'ptcgp_theme_color_engine_v1'
// 视觉优先：默认使用 node-vibrant，得到更明显的主色与光晕层次
const DEFAULT_THEME_COLOR_ENGINE: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'> = 'node-vibrant'
const DEFAULT_THEME_COLOR: [number, number, number] = [126, 168, 220]
const ENGINE_BUNDLE_SIZE_KB: Record<Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>, number> = {
  'fast-average-color': 9,
  'node-vibrant': 52
}

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

function readStorageItem(key: string): string | null {
  if (typeof window === 'undefined') {
    return null
  }
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorageItem(key: string, value: string): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // 忽略 localStorage 异常，继续使用内存缓存
  }
}

function resolveColorCacheStorage(): CardColorCacheStorage {
  if (colorCacheStorage) {
    return colorCacheStorage
  }

  const raw = readStorageItem(COLOR_CACHE_STORAGE_KEY)
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
  writeStorageItem(COLOR_CACHE_STORAGE_KEY, JSON.stringify(resolveColorCacheStorage()))
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
  const raw = readStorageItem(THEME_COLOR_ENGINE_STORAGE_KEY)
  if (raw === 'fast-average-color' || raw === 'node-vibrant') {
    return raw
  }
  return DEFAULT_THEME_COLOR_ENGINE
}

function persistPreferredEngine(engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>): void {
  writeStorageItem(THEME_COLOR_ENGINE_STORAGE_KEY, engine)
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

function percentile(sortedValues: number[], p: number): number {
  if (sortedValues.length === 0) {
    return 0
  }
  const index = Math.min(sortedValues.length - 1, Math.max(0, Math.floor((sortedValues.length - 1) * p)))
  return sortedValues[index]
}

function aggregateEngineRuns(
  engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>,
  points: EngineRunPoint[]
): EngineBenchmarkAggregate {
  const elapsedValues = points.map((item) => item.elapsedMs).sort((a, b) => a - b)
  const successCount = points.filter((item) => item.success).length
  return {
    engine,
    sampleCount: points.length,
    successCount,
    successRate: points.length > 0 ? successCount / points.length : 0,
    p50Ms: percentile(elapsedValues, 0.5),
    p95Ms: percentile(elapsedValues, 0.95),
    bundleSizeKb: ENGINE_BUNDLE_SIZE_KB[engine]
  }
}

function decideRecommendedEngine(stats: EngineBenchmarkAggregate[]): {
  engine: Extract<CardThemeColorEngine, 'fast-average-color' | 'node-vibrant'>
  reason: string
} {
  const candidates = stats.filter((item) => item.successRate >= 0.99)
  if (candidates.length === 0) {
    return {
      engine: 'fast-average-color',
      reason: '两者成功率都低于 99%，按默认引擎 fast-average-color'
    }
  }

  if (candidates.length === 1) {
    return {
      engine: candidates[0].engine,
      reason: '仅一个引擎成功率达到 99%'
    }
  }

  const [a, b] = candidates
  const faster = a.p95Ms <= b.p95Ms ? a : b
  const slower = faster.engine === a.engine ? b : a
  const p95DeltaRate = slower.p95Ms <= 0 ? 0 : Math.abs(slower.p95Ms - faster.p95Ms) / slower.p95Ms
  if (p95DeltaRate > 0.15) {
    return {
      engine: faster.engine,
      reason: 'P95 耗时差距大于 15%，优先选择更快引擎'
    }
  }

  const smallerBundle = a.bundleSizeKb <= b.bundleSizeKb ? a : b
  return {
    engine: smallerBundle.engine,
    reason: 'P95 差距小于等于 15%，优先选择包体更小引擎'
  }
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

export async function benchmarkCardThemeColorEngines(
  imageUrls: string[],
  sampleLimit = 120
): Promise<CardThemeColorBenchmarkReport> {
  const dedupedUrls: string[] = []
  const seen = new Set<string>()
  for (const rawUrl of imageUrls) {
    const url = rawUrl.trim()
    if (url.length === 0 || seen.has(url)) {
      continue
    }
    seen.add(url)
    dedupedUrls.push(url)
    if (dedupedUrls.length >= sampleLimit) {
      break
    }
  }

  const fastPoints: EngineRunPoint[] = []
  const vibrantPoints: EngineRunPoint[] = []

  for (const url of dedupedUrls) {
    const fastStart = performance.now()
    const fastRgb = await extractByFastAverageColor(url)
    fastPoints.push({
      elapsedMs: performance.now() - fastStart,
      success: fastRgb !== null
    })

    const vibrantStart = performance.now()
    const vibrantRgb = await extractByNodeVibrant(url)
    vibrantPoints.push({
      elapsedMs: performance.now() - vibrantStart,
      success: vibrantRgb !== null
    })
  }

  const fastStats = aggregateEngineRuns('fast-average-color', fastPoints)
  const vibrantStats = aggregateEngineRuns('node-vibrant', vibrantPoints)
  const decision = decideRecommendedEngine([fastStats, vibrantStats])
  persistPreferredEngine(decision.engine)

  return {
    sampleCount: dedupedUrls.length,
    stats: [fastStats, vibrantStats],
    recommendedEngine: decision.engine,
    reason: decision.reason
  }
}
