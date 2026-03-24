import { useMemo } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { HtmlFragment } from '@/components/html-fragment'
import { Button } from '@/components/ui/button'

interface ManagementPageProps {
  lang: string
  t: Record<string, string>
}

const sections = [
  { key: 'accounts', endpoint: '/management/accounts', labelKey: 'menu_accounts', fallback: 'Accounts' },
  { key: 'plans', endpoint: '/management/plans', labelKey: 'menu_plans', fallback: 'Plans' },
  { key: 'resources', endpoint: '/management/resources', labelKey: 'menu_resources', fallback: 'Resources' },
  { key: 'tasks', endpoint: '/management/tasks', labelKey: 'menu_tasks', fallback: 'Tasks' },
  { key: 'metadata', endpoint: '/management/metadata', labelKey: 'menu_metadata', fallback: 'Metadata' },
  { key: 'daily-gift', endpoint: '/management/daily-gift', labelKey: 'menu_daily_gift', fallback: 'Daily Gift' },
  { key: 'friendships', endpoint: '/management/friendships', labelKey: 'menu_friendships', fallback: 'Friendships' },
  { key: 'exchange-cards', endpoint: '/management/exchange-cards', labelKey: 'menu_exchange_cards', fallback: 'Exchange Cards' },
  { key: 'notifications', endpoint: '/management/notifications', labelKey: 'menu_notifications', fallback: 'Notifications' }
] as const

function ManagementSection({ lang, endpoint, keyName }: { lang: string; endpoint: string; keyName: string }) {
  const url = useMemo(() => `${endpoint}?lang=${encodeURIComponent(lang)}`, [endpoint, lang])
  return <HtmlFragment url={url} queryKey={['management', keyName, lang]} />
}

export function ManagementPage({ lang, t }: ManagementPageProps) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap gap-2 brutal-card p-4">
        {sections.map((section) => (
          <NavLink key={section.key} to={section.key}>
            {({ isActive }) => (
              <Button variant={isActive ? 'default' : 'outline'} size="sm" type="button">
                {t[section.labelKey] ?? section.fallback}
              </Button>
            )}
          </NavLink>
        ))}
      </div>

      <Routes>
        <Route path="/" element={<Navigate to="accounts" replace />} />
        {sections.map((section) => (
          <Route
            key={section.key}
            path={section.key}
            element={<ManagementSection lang={lang} endpoint={section.endpoint} keyName={section.key} />}
          />
        ))}
      </Routes>
    </section>
  )
}
