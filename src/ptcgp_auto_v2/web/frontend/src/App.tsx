import { useEffect } from 'react'
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

  useEffect(() => {
    // 迁移过渡期继续复用旧版事件绑定逻辑，避免局部交互回归。
    const scriptId = 'legacy-web-main'
    if (document.getElementById(scriptId)) {
      return
    }
    const script = document.createElement('script')
    script.id = scriptId
    script.type = 'module'
    script.src = '/static/js/main.js'
    document.body.appendChild(script)
  }, [])

  if (bootstrap.isLoading) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center p-4">
        <div className="brutal-card p-4 text-sm text-muted">加载中...</div>
      </main>
    )
  }

  if (bootstrap.isError || !bootstrap.data) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center p-4">
        <div className="brutal-card p-4 text-sm text-red-600">{(bootstrap.error as Error).message}</div>
      </main>
    )
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold tracking-widest">{t.app_title ?? 'PTCGP Auto Web'}</h1>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant={lang === 'en' ? 'default' : 'outline'} onClick={() => setLangParam('en', searchParams, setSearchParams)}>
            EN
          </Button>
          <Button type="button" size="sm" variant={lang === 'zh_CN' ? 'default' : 'outline'} onClick={() => setLangParam('zh_CN', searchParams, setSearchParams)}>
            中文
          </Button>
        </div>
      </header>

      <nav className="flex flex-wrap gap-2 brutal-card p-4">
        <NavLink to="/records">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button">
              {t.tab_records ?? 'RECORDS'}
            </Button>
          )}
        </NavLink>
        <NavLink to="/owned-cards">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button">
              {t.tab_owned_cards ?? 'OWNED CARDS'}
            </Button>
          )}
        </NavLink>
        <NavLink to="/management">
          {({ isActive }) => (
            <Button size="sm" variant={isActive ? 'default' : 'outline'} type="button">
              {t.tab_management ?? 'MANAGEMENT'}
            </Button>
          )}
        </NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<Navigate to="/records" replace />} />
        <Route path="/records" element={<RecordsPage lang={lang} options={bootstrap.data.options} t={t} />} />
        <Route path="/owned-cards" element={<OwnedCardsPage lang={lang} options={bootstrap.data.options} t={t} />} />
        <Route path="/management/*" element={<ManagementPage lang={lang} t={t} />} />
      </Routes>
    </main>
  )
}
