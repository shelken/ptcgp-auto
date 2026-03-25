import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { tr } from '@/lib/i18n'

interface PlaceholderPageProps {
  title: string
  t?: Record<string, string>
}

export function PlaceholderPage({ title, t }: PlaceholderPageProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">{tr(t ?? {}, 'placeholder_migration_notice', 'Migration in progress: this page will be aligned in a future iteration.')}</p>
      </CardContent>
    </Card>
  )
}
