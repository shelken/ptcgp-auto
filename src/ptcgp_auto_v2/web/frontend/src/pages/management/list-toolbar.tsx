import { SearchableSelect } from '../../components/ui/searchable-select'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  decodeSelectValue,
  encodeSelectValue
} from '../../components/ui/select'

import type {
  ManagementListDynamicOptions,
  ManagementListOption,
  ManagementListSpec,
  ManagementListState,
  ManagementListToolbarActions
} from './list-spec'
import { ListQueryControls, type SearchableOption } from './shared'

function normalizeSelectOptions(
  options: readonly string[] | readonly ManagementListOption[] | undefined,
  emptyLabel: string,
  includeEmpty = true
): ManagementListOption[] {
  const items: ManagementListOption[] = includeEmpty ? [{ value: '', label: emptyLabel }] : []
  for (const option of options ?? []) {
    if (typeof option === 'string') {
      items.push({ value: option, label: option })
      continue
    }
    items.push({ value: option.value, label: option.label })
  }
  return items
}

function readSelectOptions(
  key: string,
  dynamicOptions: ManagementListDynamicOptions | undefined,
  emptyLabel: string
): ManagementListOption[] {
  const rawOptions = dynamicOptions?.[key]
  if (!rawOptions) {
    return [{ value: '', label: emptyLabel }]
  }
  if (rawOptions.length === 0) {
    return [{ value: '', label: emptyLabel }]
  }
  if (typeof rawOptions[0] === 'string') {
    return normalizeSelectOptions(rawOptions as readonly string[], emptyLabel)
  }
  if ('searchText' in rawOptions[0]) {
    throw new Error(`筛选 ${key} 需要普通下拉选项，当前收到搜索选项`)
  }
  return normalizeSelectOptions(rawOptions as readonly ManagementListOption[], emptyLabel)
}

function readSearchableOptions(
  key: string,
  dynamicOptions: ManagementListDynamicOptions | undefined
): SearchableOption[] {
  const rawOptions = dynamicOptions?.[key]
  if (!rawOptions || rawOptions.length === 0) {
    return []
  }
  if (typeof rawOptions[0] === 'string' || !('searchText' in rawOptions[0])) {
    throw new Error(`筛选 ${key} 需要搜索选项`)
  }
  return rawOptions as SearchableOption[]
}

function readDatalistOptions(
  key: string,
  dynamicOptions: ManagementListDynamicOptions | undefined
): string[] {
  const rawOptions = dynamicOptions?.[key]
  if (!rawOptions || rawOptions.length === 0) {
    return []
  }
  if (typeof rawOptions[0] !== 'string') {
    throw new Error(`筛选 ${key} 的 datalist 只接受字符串选项`)
  }
  return [...(rawOptions as readonly string[])]
}

export function ManagementListToolbar({
  spec,
  state,
  dynamicOptions,
  actions,
  onFilterChange,
  onPageSizeChange,
  searchableLocale,
  t
}: {
  spec: ManagementListSpec
  state: ManagementListState
  dynamicOptions?: ManagementListDynamicOptions
  actions?: ManagementListToolbarActions
  onFilterChange: (key: string, value: string) => void
  onPageSizeChange: (value: number) => void
  searchableLocale: {
    searchPlaceholder: string
    emptyLabel: string
    prevPageLabel: string
    nextPageLabel: string
  }
  t: Record<string, string>
}) {
  return (
    <>
      <div className="table-toolbar-layout table-toolbar--dense management-query-controls">
        <div className="table-toolbar-zone table-toolbar-zone--left">
          {(spec.filters ?? []).map((filter) => {
            if (filter.kind === 'account-select' || filter.kind === 'searchable-select') {
              return (
                <div key={filter.key} className="table-filter-item">
                  <label className="section-subtitle">{filter.label}</label>
                  <SearchableSelect
                    value={state.filters[filter.key] ?? ''}
                    options={readSearchableOptions(filter.optionsKey, dynamicOptions)}
                    onValueChange={(value) => onFilterChange(filter.key, value)}
                    {...searchableLocale}
                    placeholder={filter.placeholder ?? filter.label}
                    pageSize={filter.pageSize ?? 12}
                    className="management-inline-select"
                  />
                </div>
              )
            }

            if (filter.kind === 'select') {
              const options = filter.options
                ? normalizeSelectOptions(filter.options, filter.emptyLabel ?? 'All', filter.includeEmpty ?? true)
                : readSelectOptions(filter.optionsKey ?? filter.key, dynamicOptions, filter.emptyLabel ?? 'All')
              return (
                <div key={filter.key} className="table-filter-item">
                  <label className="section-subtitle">{filter.label}</label>
                  <Select
                    value={encodeSelectValue(state.filters[filter.key] ?? '')}
                    onValueChange={(value) => onFilterChange(filter.key, decodeSelectValue(value))}
                  >
                    <SelectTrigger className="field-select table-control">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {options.map((option) => (
                        <SelectItem key={`${filter.key}-${option.value || 'all'}`} value={encodeSelectValue(option.value)}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            }

            const datalistKey = filter.kind === 'text' ? filter.datalistKey : undefined
            const datalistId = datalistKey
              ? `${spec.storageKey}-${filter.key}-options`
              : undefined
            return (
              <div key={filter.key} className="table-filter-item">
                <label className="section-subtitle">{filter.label}</label>
                <input
                  id={`${spec.storageKey}-${filter.key}`}
                  className="field-input table-control"
                  name={`${spec.storageKey}-${filter.key}`}
                  list={datalistId}
                  value={state.filters[filter.key] ?? ''}
                  onChange={(event) => onFilterChange(filter.key, event.target.value)}
                  placeholder={filter.placeholder ?? filter.label}
                />
                {datalistId && (
                  <datalist id={datalistId}>
                    {readDatalistOptions(datalistKey ?? filter.key, dynamicOptions).map((option) => (
                      <option key={`${filter.key}-${option}`} value={option} />
                    ))}
                  </datalist>
                )}
              </div>
            )
          })}
          {actions?.leading}
        </div>

        <div className="table-toolbar-zone table-toolbar-zone--right">
          {actions?.trailing}
        </div>
      </div>

      <ListQueryControls
        pageSize={state.pageSize}
        pageSizeOptions={[...spec.pageSizeOptions]}
        onPageSizeChange={onPageSizeChange}
        t={t}
      />
    </>
  )
}
