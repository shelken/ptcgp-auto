import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PlaceholderPageProps {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">迁移中：该页面将在后续实验中完成数据与交互对齐。</p>
      </CardContent>
    </Card>
  )
}
