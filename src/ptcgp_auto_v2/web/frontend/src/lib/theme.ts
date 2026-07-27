import { readStorageValue, writeStorageValue } from './storage'

export type ThemeMode = 'auto' | 'light' | 'dark'

const STORAGE_KEY_THEME_MODE = 'ptcgp_theme_mode'
const STORAGE_KEY_THEME_INITIALIZED = 'ptcgp_theme_initialized'
const DEFAULT_MODE: ThemeMode = 'light'

function normalizeMode(mode: string | null): ThemeMode {
  if (mode === 'light' || mode === 'dark' || mode === 'auto') {
    return mode
  }
  return DEFAULT_MODE
}

function resolveThemeScheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'auto') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return mode
}

export function loadThemeMode(): ThemeMode {
  if (!readStorageValue(STORAGE_KEY_THEME_INITIALIZED)) {
    saveThemeMode(DEFAULT_MODE)
    writeStorageValue(STORAGE_KEY_THEME_INITIALIZED, '1')
    return DEFAULT_MODE
  }
  return normalizeMode(readStorageValue(STORAGE_KEY_THEME_MODE))
}

export function saveThemeMode(mode: ThemeMode) {
  writeStorageValue(STORAGE_KEY_THEME_MODE, mode)
}

export function applyThemeMode(mode: ThemeMode) {
  const scheme = resolveThemeScheme(mode)
  const root = document.documentElement
  root.setAttribute('data-theme-mode', mode)
  root.setAttribute('data-theme-scheme', scheme)
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
