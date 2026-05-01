import type { ReactNode } from 'react'

import type { SearchableOption, SortOption } from './shared'

export type ManagementListSortOrder = 'asc' | 'desc'

export interface ManagementListOption {
  value: string
  label: string
}

interface ManagementListBaseFilterSpec {
  key: string
  label: string
  queryKey?: string
  placeholder?: string
  defaultValue?: string
}

export interface ManagementListTextFilterSpec extends ManagementListBaseFilterSpec {
  kind: 'search' | 'text'
  datalistKey?: string
}

export interface ManagementListSelectFilterSpec extends ManagementListBaseFilterSpec {
  kind: 'select'
  options?: readonly string[] | readonly ManagementListOption[]
  optionsKey?: string
  emptyLabel?: string
  includeEmpty?: boolean
}

export interface ManagementListAccountSelectFilterSpec extends ManagementListBaseFilterSpec {
  kind: 'account-select' | 'searchable-select'
  optionsKey: string
  pageSize?: number
}

export type ManagementListFilterSpec =
  | ManagementListTextFilterSpec
  | ManagementListSelectFilterSpec
  | ManagementListAccountSelectFilterSpec

export interface ManagementListSpec {
  storageKey: string
  defaultPageSize: number
  pageSizeOptions: readonly number[]
  filters?: readonly ManagementListFilterSpec[]
  queryKeys?: {
    page?: string
    pageSize?: string
    sortBy?: string
    sortOrder?: string
  }
  sort?: {
    defaultBy: string
    defaultOrder: ManagementListSortOrder
    options: readonly SortOption[]
    lockedOrderBy?: Readonly<Record<string, ManagementListSortOrder>>
  }
}

export interface ManagementListState {
  page: number
  pageSize: number
  sortBy: string
  sortOrder: ManagementListSortOrder
  filters: Record<string, string>
}

export interface ManagementListToolbarActions {
  leading?: ReactNode
  trailing?: ReactNode
}

export type ManagementListDynamicOptions = Record<
  string,
  readonly string[] | readonly ManagementListOption[] | readonly SearchableOption[]
>
