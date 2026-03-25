import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, MonitorCog, Moon, Palette, Sun } from 'lucide-react'
import { Navigate, NavLink, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { NotificationDrawer } from '@/components/notification-drawer'
import { useBootstrap } from '@/hooks/use-bootstrap'
import { fetchJson } from '@/lib/api'
import {
  alignThemeToMode,
  applyThemePreference,
  cycleThemeMode,
  DARK_THEMES,
  LIGHT_THEMES,
  THEME_MODES,
  loadThemePreference,
  mapThemeToMode,
  type ThemeMode,
  saveThemePreference,
  type ThemeName,
  type ThemePreference
} from '@/lib/theme'
import { ManagementPage } from '@/pages/management-page'
import { OwnedCardsPage } from '@/pages/owned-cards-page'
import { RecordsPage } from '@/pages/records-page'

function setLangParam(nextLang: string, searchParams: URLSearchParams, setSearchParams: (nextInit: URLSearchParams) => void) {
  const next = new URLSearchParams(searchParams)
  next.set('lang', nextLang)
  setSearchParams(next)
}

function ThemeModeIcon({ mode }: { mode: ThemeMode }) {
  if (mode === 'light') {
    return <Sun size={15} aria-hidden="true" />
  }
  if (mode === 'dark') {
    return <Moon size={15} aria-hidden="true" />
  }
  return <MonitorCog size={15} aria-hidden="true" />
}

export default function App() {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const lang = searchParams.get('lang') ?? 'zh_CN'
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [themePreference, setThemePreference] = useState<ThemePreference>(() => loadThemePreference())
  const [themePickerOpen, setThemePickerOpen] = useState(false)
  const notificationTriggerRef = useRef<HTMLButtonElement | null>(null)

  const bootstrap = useBootstrap(lang)
  const t = bootstrap.data?.t ?? {}
  const rawTranslations = (bootstrap.data?.t ?? {}) as unknown as Record<string, unknown>
  const themeLabels = (rawTranslations.themes ?? {}) as Record<string, string>
  const themeModeLabels: Record<ThemeMode, string> = {
    auto: t.theme_mode_auto ?? 'Auto',
    light: t.theme_mode_light ?? 'Light',
    dark: t.theme_mode_dark ?? 'Dark'
  }

  const notificationCountQuery = useQuery({
    queryKey: ['notification-count', lang],
    queryFn: () => fetchJson<{ unread_count: number }>(`/api/react/notifications/count?lang=${lang}`),
    refetchInterval: 30000
  })

  useEffect(() => {
    applyThemePreference(themePreference)
    saveThemePreference(themePreference)
  }, [themePreference])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onModeChange = () => {
      if (themePreference.mode === 'auto') {
        applyThemePreference(themePreference)
      }
    }
    media.addEventListener('change', onModeChange)
    return () => media.removeEventListener('change', onModeChange)
  }, [themePreference])

  useEffect(() => {
    if (!themePickerOpen) {
      return
    }
    const onClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (target.closest('[data-theme-picker-root="1"]')) {
        return
      }
      setThemePickerOpen(false)
    }
    window.addEventListener('click', onClickOutside)
    return () => window.removeEventListener('click', onClickOutside)
  }, [themePickerOpen])

  useEffect(() => {
    setNotificationOpen(false)
    setThemePickerOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!themePickerOpen) {
      return
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setThemePickerOpen(false)
      }
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [themePickerOpen])

  if (bootstrap.isLoading) {
    return (
      <main className="app-shell app-shell--center">
        <div className="surface-card text-sm text-muted">{t.label_loading ?? 'Loading...'}</div>
      </main>
    )
  }

  if (bootstrap.isError || !bootstrap.data) {
    return (
      <main className="app-shell app-shell--center">
        <div className="surface-card text-sm text-danger">{(bootstrap.error as Error).message}</div>
      </main>
    )
  }

  const assets = bootstrap.data.assets
  const appBrand = (t.app_title ?? 'PTCGP Auto').split('|').at(-1)?.trim() || 'PTCGP Auto'
  const pageTitle = (() => {
    const pathname = location.pathname
    if (pathname.startsWith('/owned-cards')) {
      return t.header_owned_cards ?? t.tab_owned_cards ?? 'OWNED CARDS'
    }
    if (pathname.startsWith('/management')) {
      return t.tab_management ?? 'MANAGEMENT'
    }
    return t.header_title ?? t.tab_records ?? 'RECORDS'
  })()

  return (
    <main className="app-shell">
      <header className="surface-card app-header">
        <div>
          <h1 className="app-title">{pageTitle} | {appBrand}</h1>
        </div>
        <div className="header-actions" data-theme-picker-root="1">
          <div className="header-icon-group">
            <button
              ref={notificationTriggerRef}
              type="button"
              className="icon-button"
              aria-label={t.notification_center ?? 'Notifications'}
              title={t.notification_center ?? 'Notifications'}
              onClick={() => setNotificationOpen(true)}
            >
              <Bell size={16} aria-hidden="true" />
              {(notificationCountQuery.data?.unread_count ?? 0) > 0 && (
                <span className="icon-badge">{notificationCountQuery.data?.unread_count}</span>
              )}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`${t.theme_mode_label ?? 'Theme Mode'}: ${themeModeLabels[themePreference.mode]}`}
              title={`${t.theme_mode_label ?? 'Theme Mode'}: ${themeModeLabels[themePreference.mode]}`}
              onClick={() =>
                setThemePreference((prev) => {
                  const nextMode = cycleThemeMode(prev.mode)
                  return {
                    mode: nextMode,
                    theme: alignThemeToMode(nextMode, prev.theme)
                  }
                })
              }
            >
              <ThemeModeIcon mode={themePreference.mode} />
            </button>
            <button
              type="button"
              className={`icon-button ${themePickerOpen ? 'is-active' : ''}`}
              aria-label={t.theme_label ?? 'Theme'}
              title={t.theme_label ?? 'Theme'}
              aria-expanded={themePickerOpen}
              aria-haspopup="dialog"
              onClick={() => setThemePickerOpen((prev) => !prev)}
            >
              <Palette size={16} aria-hidden="true" />
            </button>
          </div>
          {themePickerOpen && (
            <div className="theme-popover-react" role="dialog" aria-label={t.theme_label ?? 'Theme'}>
              <div className="theme-popover-head">
                <div className="theme-section-title">{t.theme_label ?? 'Theme'}</div>
                <div className="text-xs text-muted">
                  {t.theme_mode_label ?? 'Mode'}: {themeModeLabels[themePreference.mode]}
                </div>
              </div>
              <div className="theme-mode-grid" role="radiogroup" aria-label={t.theme_mode_label ?? 'Theme Mode'}>
                {THEME_MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`theme-mode-pill ${themePreference.mode === mode ? 'is-active' : ''}`}
                    role="radio"
                    aria-checked={themePreference.mode === mode}
                    onClick={() =>
                      setThemePreference((prev) => ({
                        mode,
                        theme: alignThemeToMode(mode, prev.theme)
                      }))
                    }
                  >
                    <ThemeModeIcon mode={mode} />
                    <span>{themeModeLabels[mode]}</span>
                  </button>
                ))}
              </div>
              <div className="theme-popover-grid">
                <div className="theme-section">
                  <div className="theme-section-title">{t.theme_group_light ?? 'Light Themes'}</div>
                  <div className="theme-options">
                    {LIGHT_THEMES.map((theme) => (
                      <Button
                        key={theme}
                        type="button"
                        size="sm"
                        className="theme-option-button"
                        variant={themePreference.theme === theme ? 'default' : 'outline'}
                        onClick={() =>
                          setThemePreference({
                            mode: mapThemeToMode(theme),
                            theme: theme as ThemeName
                          })
                        }
                      >
                        {themeLabels[theme] ?? theme}
                      </Button>
                    ))}
                  </div>
                </div>
                <div className="theme-section">
                  <div className="theme-section-title">{t.theme_group_dark ?? 'Dark Themes'}</div>
                  <div className="theme-options">
                    {DARK_THEMES.map((theme) => (
                      <Button
                        key={theme}
                        type="button"
                        size="sm"
                        className="theme-option-button"
                        variant={themePreference.theme === theme ? 'default' : 'outline'}
                        onClick={() =>
                          setThemePreference({
                            mode: mapThemeToMode(theme),
                            theme: theme as ThemeName
                          })
                        }
                      >
                        {themeLabels[theme] ?? theme}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
          <div className="header-lang-group">
            <Button type="button" size="sm" variant={lang === 'en' ? 'default' : 'outline'} onClick={() => setLangParam('en', searchParams, setSearchParams)}>
              {t.lang_en ?? 'EN'}
            </Button>
            <Button type="button" size="sm" variant={lang === 'zh_CN' ? 'default' : 'outline'} onClick={() => setLangParam('zh_CN', searchParams, setSearchParams)}>
              {t.lang_zh_cn ?? '中文'}
            </Button>
          </div>
        </div>
      </header>

      <nav className="surface-card tab-nav">
        <NavLink to="/records">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button" className="min-w-28">
              {t.tab_records ?? 'RECORDS'}
            </Button>
          )}
        </NavLink>
        <NavLink to="/owned-cards">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button" className="min-w-28">
              {t.tab_owned_cards ?? 'OWNED CARDS'}
            </Button>
          )}
        </NavLink>
        <NavLink to="/management">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button" className="min-w-28">
              {t.tab_management ?? 'MANAGEMENT'}
            </Button>
          )}
        </NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<Navigate to="/records" replace />} />
        <Route path="/records" element={<RecordsPage lang={lang} options={bootstrap.data.options} assets={assets} t={t} />} />
        <Route path="/owned-cards" element={<OwnedCardsPage lang={lang} options={bootstrap.data.options} assets={assets} t={t} />} />
        <Route path="/management/*" element={<ManagementPage lang={lang} t={t} assets={assets} />} />
      </Routes>

      <NotificationDrawer
        lang={lang}
        t={t}
        open={notificationOpen}
        onOpenChange={setNotificationOpen}
        restoreFocusRef={notificationTriggerRef}
      />
    </main>
  )
}
