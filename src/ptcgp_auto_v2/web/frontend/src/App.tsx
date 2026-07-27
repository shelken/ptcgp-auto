import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, Desktop, Moon, Sun } from '@phosphor-icons/react'
import { Navigate, NavLink, Route, Routes, useLocation, type SetURLSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { NotificationDrawer } from '@/components/notification-drawer'
import { useBootstrap } from '@/hooks/use-bootstrap'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { fetchJson } from '@/lib/api'
import {
  applyThemeMode,
  cycleThemeMode,
  loadThemeMode,
  saveThemeMode,
  type ThemeMode
} from '@/lib/theme'

const RecordsPage = lazy(async () => {
  const mod = await import('@/pages/records-page')
  return { default: mod.RecordsPage }
})
const OwnedCardsPage = lazy(async () => {
  const mod = await import('@/pages/owned-cards-page')
  return { default: mod.OwnedCardsPage }
})
const ManagementPage = lazy(async () => {
  const mod = await import('@/pages/management-page')
  return { default: mod.ManagementPage }
})

function setLangParam(nextLang: string, searchParams: URLSearchParams, setSearchParams: SetURLSearchParams) {
  const next = new URLSearchParams(searchParams)
  next.set('lang', nextLang)
  setSearchParams(next, { replace: true, preventScrollReset: true })
}

export function buildNavTo(path: string, lang: string) {
  return `${path}?lang=${lang}`
}

export function buildRootRedirectTo(search: string) {
  return { pathname: '/records', search }
}

function ThemeModeIcon({ mode }: { mode: ThemeMode }) {
  if (mode === 'light') {
    return <Sun size={15} aria-hidden="true" />
  }
  if (mode === 'dark') {
    return <Moon size={15} aria-hidden="true" />
  }
  return <Desktop size={15} aria-hidden="true" />
}

function titleCaseLabel(value: string) {
  return value
    .toLowerCase()
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export default function App() {
  const [searchParams, setSearchParams] = usePersistedSearchParams()
  const location = useLocation()
  const lang = searchParams.get('lang') ?? 'zh_CN'
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => loadThemeMode())
  const notificationTriggerRef = useRef<HTMLButtonElement | null>(null)

  const bootstrap = useBootstrap(lang)
  const t = bootstrap.data?.t ?? {}
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
    applyThemeMode(themeMode)
    saveThemeMode(themeMode)
  }, [themeMode])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onModeChange = () => {
      if (themeMode === 'auto') {
        applyThemeMode(themeMode)
      }
    }
    media.addEventListener('change', onModeChange)
    return () => media.removeEventListener('change', onModeChange)
  }, [themeMode])

  if (bootstrap.isLoading) {
    return (
      <main className="app-shell app-shell--center">
        <div className="surface-card state-block">
          <div className="state-skeleton" aria-hidden="true" />
          <p className="state-copy">{t.label_loading ?? '加载中'}</p>
        </div>
      </main>
    )
  }

  if (bootstrap.isError || !bootstrap.data) {
    return (
      <main className="app-shell app-shell--center">
        <div className="surface-card state-block state-block--error">
          <p className="state-copy">{(bootstrap.error as Error).message}</p>
        </div>
      </main>
    )
  }

  const assets = bootstrap.data.assets
  const options = bootstrap.data.options
  const appBrand = (t.app_title ?? 'PTCGP Auto').split('|').at(-1)?.trim() || 'PTCGP Auto'
  const pageTitle = (() => {
    const pathname = location.pathname
    if (pathname.startsWith('/owned-cards')) {
      return titleCaseLabel(t.header_owned_cards ?? t.tab_owned_cards ?? 'Owned cards')
    }
    if (pathname.startsWith('/management')) {
      return titleCaseLabel(t.tab_management ?? 'Management')
    }
    return titleCaseLabel(t.header_title ?? t.tab_records ?? 'Records')
  })()

  return (
    <main className="app-shell">
      <header className="surface-card app-header">
        <div className="app-brand-block">
          <p className="app-brand">{appBrand}</p>
          <h1 className="app-title">{pageTitle}</h1>
        </div>
        <div className="header-actions">
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
              aria-label={`${t.theme_mode_label ?? 'Theme Mode'}: ${themeModeLabels[themeMode]}`}
              title={`${t.theme_mode_label ?? 'Theme Mode'}: ${themeModeLabels[themeMode]}`}
              onClick={() => setThemeMode((prev) => cycleThemeMode(prev))}
            >
              <ThemeModeIcon mode={themeMode} />
            </button>
          </div>
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

      <nav className="surface-card tab-nav" aria-label={t.nav_label ?? 'Main'}>
        <NavLink to={buildNavTo('/records', lang)} className={({ isActive }) => `tab-link${isActive ? ' is-active' : ''}`}>
          {titleCaseLabel(t.tab_records ?? 'Records')}
        </NavLink>
        <NavLink to={buildNavTo('/owned-cards', lang)} className={({ isActive }) => `tab-link${isActive ? ' is-active' : ''}`}>
          {titleCaseLabel(t.tab_owned_cards ?? 'Owned cards')}
        </NavLink>
        <NavLink to={buildNavTo('/management', lang)} className={({ isActive }) => `tab-link${isActive ? ' is-active' : ''}`}>
          {titleCaseLabel(t.tab_management ?? 'Management')}
        </NavLink>
      </nav>

      <Suspense
        fallback={(
          <div className="surface-card state-block">
            <div className="state-skeleton" aria-hidden="true" />
            <p className="state-copy">{t.label_loading ?? '加载中'}</p>
          </div>
        )}
      >
        <Routes>
          <Route path="/" element={<Navigate to={buildRootRedirectTo(location.search)} replace />} />
          <Route path="/records" element={<RecordsPage lang={lang} options={options} assets={assets} t={t} />} />
          <Route path="/owned-cards" element={<OwnedCardsPage lang={lang} options={options} assets={assets} t={t} />} />
          <Route path="/management/*" element={<ManagementPage lang={lang} t={t} assets={assets} />} />
        </Routes>
      </Suspense>

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
