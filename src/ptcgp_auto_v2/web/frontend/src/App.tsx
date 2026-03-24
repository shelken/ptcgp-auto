import { Navigate, NavLink, Route, Routes } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { PlaceholderPage } from '@/pages/placeholder-page'

const appRoutes = [
  { path: '/records', label: 'Records' },
  { path: '/owned-cards', label: 'Owned Cards' },
  { path: '/management/accounts', label: 'Accounts' },
  { path: '/management/plans', label: 'Plans' },
  { path: '/management/resources', label: 'Resources' },
  { path: '/management/tasks', label: 'Tasks' },
  { path: '/management/metadata', label: 'Metadata' },
  { path: '/management/daily-gift', label: 'Daily Gift' },
  { path: '/management/friendships', label: 'Friendships' },
  { path: '/management/exchange-cards', label: 'Exchange Cards' },
  { path: '/management/notifications', label: 'Notifications' }
]

function LinkButton({ to, label }: { to: string; label: string }) {
  return (
    <NavLink to={to}>
      {({ isActive }) => (
        <Button variant={isActive ? 'default' : 'outline'} size="sm">
          {label}
        </Button>
      )}
    </NavLink>
  )
}

export default function App() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 p-4">
      <header className="flex flex-wrap gap-2">
        {appRoutes.map((item) => (
          <LinkButton key={item.path} to={item.path} label={item.label} />
        ))}
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/records" replace />} />
        {appRoutes.map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage title={item.label} />} />
        ))}
      </Routes>
    </main>
  )
}
