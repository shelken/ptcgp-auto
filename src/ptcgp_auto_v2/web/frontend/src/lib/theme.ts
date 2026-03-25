export type ThemeMode = 'auto' | 'light' | 'dark'
export const THEME_MODES = ['auto', 'light', 'dark'] as const

export const LIGHT_THEMES = ['brutalist', 'organic', 'playful', 'editorial', 'pastel'] as const
export const DARK_THEMES = ['retro', 'art_deco', 'luxury'] as const
export type ThemeName = (typeof LIGHT_THEMES)[number] | (typeof DARK_THEMES)[number]

export interface ThemePreference {
  mode: ThemeMode
  theme: ThemeName
}

const STORAGE_KEY_THEME = 'ptcgp_theme'
const STORAGE_KEY_THEME_MODE = 'ptcgp_theme_mode'
const STORAGE_KEY_LAST_LIGHT = 'ptcgp_last_light_theme'
const STORAGE_KEY_LAST_DARK = 'ptcgp_last_dark_theme'

const DEFAULT_LIGHT_THEME: ThemeName = 'brutalist'
const DEFAULT_DARK_THEME: ThemeName = 'retro'
const THEME_FONT_LINK_PREFIX = 'theme-font-'

const THEME_FONT_STYLESHEET: Partial<Record<ThemeName, string>> = {
  organic: 'https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&display=swap',
  luxury: 'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap',
  playful: 'https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap',
  editorial: 'https://fonts.googleapis.com/css2?family=Bodoni+Moda:wght@400;700&display=swap',
  art_deco: 'https://fonts.googleapis.com/css2?family=Limelight&display=swap',
  pastel: 'https://fonts.googleapis.com/css2?family=Quicksand:wght@400;700&display=swap'
}

function isLightTheme(theme: string): theme is (typeof LIGHT_THEMES)[number] {
  return (LIGHT_THEMES as readonly string[]).includes(theme)
}

function isDarkTheme(theme: string): theme is (typeof DARK_THEMES)[number] {
  return (DARK_THEMES as readonly string[]).includes(theme)
}

function normalizeTheme(theme: string | null): ThemeName {
  if (theme && (isLightTheme(theme) || isDarkTheme(theme))) {
    return theme
  }
  return DEFAULT_LIGHT_THEME
}

function normalizeMode(mode: string | null): ThemeMode {
  if (mode === 'light' || mode === 'dark' || mode === 'auto') {
    return mode
  }
  return 'auto'
}

function getLastLightTheme(): ThemeName {
  const stored = window.localStorage.getItem(STORAGE_KEY_LAST_LIGHT)
  if (stored && isLightTheme(stored)) {
    return stored
  }
  return DEFAULT_LIGHT_THEME
}

function getLastDarkTheme(): ThemeName {
  const stored = window.localStorage.getItem(STORAGE_KEY_LAST_DARK)
  if (stored && isDarkTheme(stored)) {
    return stored
  }
  return DEFAULT_DARK_THEME
}

function rememberThemeByGroup(theme: ThemeName) {
  if (isLightTheme(theme)) {
    window.localStorage.setItem(STORAGE_KEY_LAST_LIGHT, theme)
    return
  }
  window.localStorage.setItem(STORAGE_KEY_LAST_DARK, theme)
}

function ensureThemeFontStylesheet(theme: ThemeName) {
  const href = THEME_FONT_STYLESHEET[theme]
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

export function alignThemeToMode(mode: ThemeMode, theme: ThemeName): ThemeName {
  if (mode === 'auto') {
    return theme
  }
  if (mode === 'light') {
    return isLightTheme(theme) ? theme : getLastLightTheme()
  }
  return isDarkTheme(theme) ? theme : getLastDarkTheme()
}

export function resolveThemeByMode(mode: ThemeMode, theme: ThemeName): ThemeName {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  if (mode === 'auto') {
    return prefersDark ? DEFAULT_DARK_THEME : DEFAULT_LIGHT_THEME
  }
  if (mode === 'light') {
    return isLightTheme(theme) ? theme : DEFAULT_LIGHT_THEME
  }
  return isDarkTheme(theme) ? theme : DEFAULT_DARK_THEME
}

export function loadThemePreference(): ThemePreference {
  const mode = normalizeMode(window.localStorage.getItem(STORAGE_KEY_THEME_MODE))
  const theme = normalizeTheme(window.localStorage.getItem(STORAGE_KEY_THEME))
  return { mode, theme: alignThemeToMode(mode, theme) }
}

export function saveThemePreference(preference: ThemePreference) {
  window.localStorage.setItem(STORAGE_KEY_THEME_MODE, preference.mode)
  window.localStorage.setItem(STORAGE_KEY_THEME, preference.theme)
  rememberThemeByGroup(preference.theme)
}

export function applyThemePreference(preference: ThemePreference) {
  const appliedTheme = resolveThemeByMode(preference.mode, preference.theme)
  const root = document.documentElement
  root.setAttribute('data-theme', appliedTheme)
  root.setAttribute('data-theme-mode', preference.mode)
  ensureThemeFontStylesheet(appliedTheme)
  rememberThemeByGroup(appliedTheme)
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

export function mapThemeToMode(theme: ThemeName): ThemeMode {
  if (isLightTheme(theme)) {
    return 'light'
  }
  return 'dark'
}
