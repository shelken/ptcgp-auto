import { Navigate, NavLink, Route, Routes, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useBootstrap } from '@/hooks/use-bootstrap'
import { ManagementPage } from '@/pages/management-page'
import { OwnedCardsPage } from '@/pages/owned-cards-page'
import { RecordsPage } from '@/pages/records-page'

function setLangParam(nextLang: string, searchParams: URLSearchParams, setSearchParams: (nextInit: URLSearchParams) => void) {
  const next = new URLSearchParams(searchParams)
  next.set('lang', nextLang)
  setSearchParams(next)
}

export default function App() {
  const [searchParams, setSearchParams] = useSearchParams()
  const lang = searchParams.get('lang') ?? 'zh_CN'

  const bootstrap = useBootstrap(lang)
  const t = bootstrap.data?.t ?? {}

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

  return (
    <main className="app-shell">
      <header className="surface-card app-header">
        <div>
          <h1 className="app-title">{t.app_title ?? 'PTCGP Auto Web'}</h1>
          <p className="text-xs text-muted">{t.loading_text ?? '自动化控制台'}</p>
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant={lang === 'en' ? 'default' : 'outline'} onClick={() => setLangParam('en', searchParams, setSearchParams)}>
            EN
          </Button>
          <Button type="button" size="sm" variant={lang === 'zh_CN' ? 'default' : 'outline'} onClick={() => setLangParam('zh_CN', searchParams, setSearchParams)}>
            中文
          </Button>
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
        <Route path="/management/*" element={<ManagementPage lang={lang} t={t} />} />
      </Routes>
    </main>
  )
}
