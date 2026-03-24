import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { HtmlFragment } from '@/components/html-fragment'
import type { BootstrapOptions } from '@/types/api'

interface OwnedCardsPageProps {
  lang: string
  options: BootstrapOptions
  t: Record<string, string>
}

function toggleItems(current: string[], value: string): string[] {
  if (current.includes(value)) {
    return current.filter((item) => item !== value)
  }
  return [...current, value]
}

function appendArray(params: URLSearchParams, key: string, values: string[]) {
  values.forEach((value) => params.append(key, value))
}

export function OwnedCardsPage({ lang, options, t }: OwnedCardsPageProps) {
  const [selectedRarity, setSelectedRarity] = useState<string[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [selectedElements, setSelectedElements] = useState<string[]>([])
  const [selectedSetCodes, setSelectedSetCodes] = useState<string[]>([])
  const [selectedPackNames, setSelectedPackNames] = useState<string[]>([])
  const [sortBy, setSortBy] = useState('acquired')
  const [ownershipScope, setOwnershipScope] = useState('owned')

  const queryUrl = useMemo(() => {
    const params = new URLSearchParams()
    params.set('page', '0')
    params.set('page_size', '60')
    params.set('lang', lang)
    params.set('sort_by', sortBy)
    params.set('ownership_scope', ownershipScope)
    appendArray(params, 'rarity', selectedRarity)
    appendArray(params, 'card_type', selectedTypes)
    appendArray(params, 'element', selectedElements)
    appendArray(params, 'set_code', selectedSetCodes)
    appendArray(params, 'pack_name', selectedPackNames)
    return `/api/owned-cards?${params.toString()}`
  }, [
    lang,
    ownershipScope,
    selectedElements,
    selectedPackNames,
    selectedRarity,
    selectedSetCodes,
    selectedTypes,
    sortBy
  ])

  const statsUrl = useMemo(() => {
    const params = new URLSearchParams()
    params.set('lang', lang)
    params.set('ownership_scope', ownershipScope)
    appendArray(params, 'rarity', selectedRarity)
    appendArray(params, 'card_type', selectedTypes)
    appendArray(params, 'element', selectedElements)
    appendArray(params, 'set_code', selectedSetCodes)
    appendArray(params, 'pack_name', selectedPackNames)
    return `/api/owned-cards/stats?${params.toString()}`
  }, [lang, ownershipScope, selectedElements, selectedPackNames, selectedRarity, selectedSetCodes, selectedTypes])

  return (
    <section className="space-y-4">
      <div className="brutal-card p-4 space-y-4">
        <h2 className="font-bold tracking-widest uppercase text-sm">{t.filter_title ?? 'Filters'}</h2>

        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant={ownershipScope === 'owned' ? 'default' : 'outline'} onClick={() => setOwnershipScope('owned')}>
            {t.owned_scope_owned ?? 'Owned'}
          </Button>
          <Button type="button" size="sm" variant={ownershipScope === 'missing' ? 'default' : 'outline'} onClick={() => setOwnershipScope('missing')}>
            {t.owned_scope_missing ?? 'Missing'}
          </Button>
          <Button type="button" size="sm" variant={ownershipScope === 'all' ? 'default' : 'outline'} onClick={() => setOwnershipScope('all')}>
            {t.owned_scope_all ?? 'All'}
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant={sortBy === 'acquired' ? 'default' : 'outline'} onClick={() => setSortBy('acquired')}>
            {t.owned_sort_acquired ?? 'Acquired'}
          </Button>
          <Button type="button" size="sm" variant={sortBy === 'rarity' ? 'default' : 'outline'} onClick={() => setSortBy('rarity')}>
            {t.owned_sort_rarity ?? 'Rarity'}
          </Button>
          <Button type="button" size="sm" variant={sortBy === 'count' ? 'default' : 'outline'} onClick={() => setSortBy('count')}>
            {t.owned_sort_count ?? 'Count'}
          </Button>
        </div>

        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-widest text-muted">{t.filter_rarity ?? 'Rarity'}</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.rarities.map((rarity) => (
              <Button
                key={rarity}
                type="button"
                size="sm"
                variant={selectedRarity.includes(rarity) ? 'default' : 'outline'}
                onClick={() => setSelectedRarity((prev) => toggleItems(prev, rarity))}
              >
                {t[`rarity_${rarity}`] ?? rarity}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-widest text-muted">{t.filter_type ?? 'Type'}</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.card_types.map((cardType) => (
              <Button
                key={cardType}
                type="button"
                size="sm"
                variant={selectedTypes.includes(cardType) ? 'default' : 'outline'}
                onClick={() => setSelectedTypes((prev) => toggleItems(prev, cardType))}
              >
                {t[`type_${cardType}`] ?? cardType}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-widest text-muted">{t.filter_set ?? 'Set'}</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.card_sets.map((item) => (
              <Button
                key={item.code}
                type="button"
                size="sm"
                variant={selectedSetCodes.includes(item.code) ? 'default' : 'outline'}
                onClick={() => setSelectedSetCodes((prev) => toggleItems(prev, item.code))}
              >
                {item.display_name}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-widest text-muted">{t.filter_pack ?? 'Pack'}</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.packs.map((item) => (
              <Button
                key={item.name}
                type="button"
                size="sm"
                variant={selectedPackNames.includes(item.name) ? 'default' : 'outline'}
                onClick={() => setSelectedPackNames((prev) => toggleItems(prev, item.name))}
              >
                {item.display_name}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-widest text-muted">{t.filter_element ?? 'Element'}</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.elements.map((item) => (
              <Button
                key={item}
                type="button"
                size="sm"
                variant={selectedElements.includes(item) ? 'default' : 'outline'}
                onClick={() => setSelectedElements((prev) => toggleItems(prev, item))}
              >
                {t[`element_${item}`] ?? item}
              </Button>
            ))}
          </div>
        </details>
      </div>

      <HtmlFragment
        url={statsUrl}
        queryKey={['owned-stats', lang, ownershipScope, sortBy, selectedRarity.join(','), selectedTypes.join(','), selectedSetCodes.join(','), selectedPackNames.join(','), selectedElements.join(',')]}
      />

      <HtmlFragment
        url={queryUrl}
        queryKey={['owned-list', lang, ownershipScope, sortBy, selectedRarity.join(','), selectedTypes.join(','), selectedSetCodes.join(','), selectedPackNames.join(','), selectedElements.join(',')]}
      />
    </section>
  )
}
