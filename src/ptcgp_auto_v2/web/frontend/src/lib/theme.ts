export type ThemeMode = 'auto' | 'light' | 'dark'
type ThemeScheme = 'light' | 'dark'
export type ThemeAvailability = 'light' | 'dark' | 'both'
export const THEME_MODES = ['auto', 'light', 'dark'] as const

interface ThemeRegistrationBase {
  id: string
  availability: ThemeAvailability
  fallbackGroup: string
  fontStylesheet?: string
}

export const THEME_REGISTRY = [
  { id: 'brutalist', availability: 'light', fallbackGroup: 'base' },
  {
    id: 'organic',
    availability: 'light',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&display=swap'
  },
  {
    id: 'playful',
    availability: 'light',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap'
  },
  {
    id: 'editorial',
    availability: 'light',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Bodoni+Moda:wght@400;700&display=swap'
  },
  {
    id: 'pastel',
    availability: 'light',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Quicksand:wght@400;700&display=swap'
  },
  {
    id: 'clay_vibrant',
    availability: 'both',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@400;500;700&family=Fira+Code:wght@400;500;700&display=swap'
  },
  { id: 'retro', availability: 'dark', fallbackGroup: 'base' },
  {
    id: 'art_deco',
    availability: 'dark',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Limelight&display=swap'
  },
  {
    id: 'luxury',
    availability: 'dark',
    fallbackGroup: 'base',
    fontStylesheet: 'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap'
  }
] as const satisfies readonly ThemeRegistrationBase[]

export type ThemeName = (typeof THEME_REGISTRY)[number]['id']

interface ThemeRegistration {
  id: ThemeName
  availability: ThemeAvailability
  fallbackGroup: string
  fontStylesheet?: string
}

export interface ThemePreference {
  mode: ThemeMode
  theme: ThemeName
}

const STORAGE_KEY_THEME = 'ptcgp_theme'
const STORAGE_KEY_THEME_MODE = 'ptcgp_theme_mode'
const STORAGE_KEY_LAST_LIGHT = 'ptcgp_last_light_theme'
const STORAGE_KEY_LAST_DARK = 'ptcgp_last_dark_theme'
const STORAGE_KEY_THEME_INITIALIZED = 'ptcgp_theme_initialized'

const DEFAULT_LIGHT_THEME: ThemeName = 'brutalist'
const DEFAULT_DARK_THEME: ThemeName = 'retro'
const THEME_FONT_LINK_PREFIX = 'theme-font-'

const THEME_DEFINITIONS: Record<ThemeName, ThemeRegistration> = Object.fromEntries(
  THEME_REGISTRY.map((theme) => [theme.id, theme])
) as Record<ThemeName, ThemeRegistration>

const THEME_INDICES: Record<ThemeName, number> = Object.fromEntries(
  THEME_REGISTRY.map((theme, index) => [theme.id, index])
) as Record<ThemeName, number>

function themeSupportsScheme(theme: ThemeName, scheme: ThemeScheme): boolean {
  const availability = THEME_DEFINITIONS[theme].availability
  return availability === 'both' || availability === scheme
}

function resolveDefaultThemeByScheme(scheme: ThemeScheme): ThemeName {
  return scheme === 'light' ? DEFAULT_LIGHT_THEME : DEFAULT_DARK_THEME
}

function isThemeName(theme: string): theme is ThemeName {
  return theme in THEME_DEFINITIONS
}

function findNearestThemeInFallbackGroup(theme: ThemeName, scheme: ThemeScheme): ThemeName | null {
  const source = THEME_DEFINITIONS[theme]
  const sourceIndex = THEME_INDICES[theme]
  let nearest: ThemeName | null = null
  let nearestDistance = Number.POSITIVE_INFINITY
  let nearestIndex = Number.POSITIVE_INFINITY

  // 只在同 fallbackGroup 内按注册顺序寻找最近可用主题
  for (const candidate of THEME_REGISTRY) {
    if (candidate.fallbackGroup !== source.fallbackGroup || !themeSupportsScheme(candidate.id, scheme)) {
      continue
    }
    const candidateIndex = THEME_INDICES[candidate.id]
    const distance = Math.abs(candidateIndex - sourceIndex)
    if (distance < nearestDistance || (distance === nearestDistance && candidateIndex < nearestIndex)) {
      nearest = candidate.id
      nearestDistance = distance
      nearestIndex = candidateIndex
    }
  }

  return nearest
}

function resolveThemeByScheme(theme: ThemeName, scheme: ThemeScheme): ThemeName {
  if (themeSupportsScheme(theme, scheme)) {
    return theme
  }
  return findNearestThemeInFallbackGroup(theme, scheme) ?? resolveDefaultThemeByScheme(scheme)
}

function normalizeTheme(theme: string | null): ThemeName {
  if (theme && isThemeName(theme)) {
    return theme
  }
  return DEFAULT_LIGHT_THEME
}

function normalizeMode(mode: string | null): ThemeMode {
  if (mode === 'light' || mode === 'dark' || mode === 'auto') {
    return mode
  }
  return 'light'
}

function rememberThemeByScheme(theme: ThemeName, scheme: ThemeScheme) {
  if (scheme === 'light') {
    window.localStorage.setItem(STORAGE_KEY_LAST_LIGHT, theme)
    return
  }
  window.localStorage.setItem(STORAGE_KEY_LAST_DARK, theme)
}

function rememberThemeByAvailability(theme: ThemeName) {
  const availability = THEME_DEFINITIONS[theme].availability
  if (availability === 'light') {
    rememberThemeByScheme(theme, 'light')
    return
  }
  if (availability === 'dark') {
    rememberThemeByScheme(theme, 'dark')
    return
  }
  rememberThemeByScheme(theme, 'light')
  rememberThemeByScheme(theme, 'dark')
}

function ensureThemeFontStylesheet(theme: ThemeName) {
  const href = THEME_DEFINITIONS[theme].fontStylesheet
  if (!href) {
    return
  }
  const linkId = `${THEME_FONT_LINK_PREFIX}${theme}`
  if (document.getElementById(linkId)) {
    return
  }
  const link = document.createElement('link')
  link.id = linkId
  link.rel = 'stylesheet'
  link.href = href
  document.head.appendChild(link)
}

export function listThemesByAvailability(availability: ThemeAvailability): ThemeName[] {
  return THEME_REGISTRY.filter((theme) => theme.availability === availability).map((theme) => theme.id)
}

function resolveThemeScheme(mode: ThemeMode): ThemeScheme {
  if (mode === 'auto') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return mode
}

export function alignThemeToMode(mode: ThemeMode, theme: ThemeName): ThemeName {
  if (mode === 'auto') {
    return theme
  }
  return resolveThemeByScheme(theme, mode)
}

function resolveThemeByMode(mode: ThemeMode, theme: ThemeName): ThemeName {
  const themeScheme = resolveThemeScheme(mode)
  // auto 模式仍优先使用用户选择的主题，再按 scheme 回退
  return resolveThemeByScheme(theme, themeScheme)
}

export function loadThemePreference(): ThemePreference {
  if (!window.localStorage.getItem(STORAGE_KEY_THEME_INITIALIZED)) {
    const initial: ThemePreference = { mode: 'light', theme: DEFAULT_LIGHT_THEME }
    saveThemePreference(initial)
    window.localStorage.setItem(STORAGE_KEY_THEME_INITIALIZED, '1')
    return initial
  }
  const mode = normalizeMode(window.localStorage.getItem(STORAGE_KEY_THEME_MODE))
  const theme = normalizeTheme(window.localStorage.getItem(STORAGE_KEY_THEME))
  return { mode, theme: alignThemeToMode(mode, theme) }
}

export function saveThemePreference(preference: ThemePreference) {
  window.localStorage.setItem(STORAGE_KEY_THEME_MODE, preference.mode)
  window.localStorage.setItem(STORAGE_KEY_THEME, preference.theme)
  rememberThemeByAvailability(preference.theme)
}

export function applyThemePreference(preference: ThemePreference) {
  const themeScheme = resolveThemeScheme(preference.mode)
  const appliedTheme = resolveThemeByMode(preference.mode, preference.theme)
  const root = document.documentElement
  root.setAttribute('data-theme', appliedTheme)
  root.setAttribute('data-theme-mode', preference.mode)
  root.setAttribute('data-theme-scheme', themeScheme)
  ensureThemeFontStylesheet(appliedTheme)
  rememberThemeByScheme(appliedTheme, themeScheme)
}

export function cycleThemeMode(current: ThemeMode): ThemeMode {
  if (current === 'auto') {
    return 'light'
  }
  if (current === 'light') {
    return 'dark'
  }
  return 'auto'
}

export function mapThemeToMode(theme: ThemeName, currentMode: ThemeMode = 'light'): ThemeMode {
  const availability = THEME_DEFINITIONS[theme].availability
  if (availability === 'light') {
    return 'light'
  }
  if (availability === 'dark') {
    return 'dark'
  }
  return currentMode
}
