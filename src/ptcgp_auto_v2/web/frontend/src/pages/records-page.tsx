import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { HtmlFragment } from '@/components/html-fragment'
import type { BootstrapOptions } from '@/types/api'

interface RecordsPageProps {
  lang: string
  options: BootstrapOptions
  t: Record<string, string>
}

function appendArrayParams(params: URLSearchParams, key: string, values: string[]) {
  values.forEach((value) => {
    params.append(key, value)
  })
}

export function RecordsPage({ lang, options, t }: RecordsPageProps) {
  const [selectedRarity, setSelectedRarity] = useState<string[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])

  const url = useMemo(() => {
    const params = new URLSearchParams()
    params.set('page', '0')
    params.set('page_size', '10')
    params.set('lang', lang)
    appendArrayParams(params, 'rarity', selectedRarity)
    appendArrayParams(params, 'card_type', selectedTypes)
    return `/api/records?${params.toString()}`
  }, [lang, selectedRarity, selectedTypes])

  function toggleItem(current: string[], value: string): string[] {
    if (current.includes(value)) {
      return current.filter((item) => item !== value)
    }
    return [...current, value]
  }

  return (
    <section className="space-y-4">
      <div className="brutal-card p-4 space-y-4">
        <h2 className="font-bold tracking-widest uppercase text-sm">{t.filter_title ?? 'Filters'}</h2>

        <div className="space-y-2">
          <div className="text-xs text-muted uppercase tracking-widest">{t.filter_rarity ?? 'Rarity'}</div>
          <div className="flex flex-wrap gap-2">
            {options.rarities.map((rarity) => (
              <Button
                key={rarity}
                type="button"
                size="sm"
                variant={selectedRarity.includes(rarity) ? 'default' : 'outline'}
                onClick={() => setSelectedRarity((prev) => toggleItem(prev, rarity))}
              >
                {t[`rarity_${rarity}`] ?? rarity}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs text-muted uppercase tracking-widest">{t.filter_type ?? 'Type'}</div>
          <div className="flex flex-wrap gap-2">
            {options.card_types.map((cardType) => (
              <Button
                key={cardType}
                type="button"
                size="sm"
                variant={selectedTypes.includes(cardType) ? 'default' : 'outline'}
                onClick={() => setSelectedTypes((prev) => toggleItem(prev, cardType))}
              >
                {t[`type_${cardType}`] ?? cardType}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <HtmlFragment
        url={url}
        queryKey={['records', lang, selectedRarity.join(','), selectedTypes.join(',')]}
        className="space-y-2"
      />
    </section>
  )
}
