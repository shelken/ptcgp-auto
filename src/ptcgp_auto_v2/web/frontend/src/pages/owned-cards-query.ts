import { parseSearchList } from '../lib/list-utils'

export type OwnedCardsViewMode = 'grid' | 'list'

interface OwnedCardsSearchState {
  accountQuery: string
  cardNameQuery: string
  selectedRarity: string[]
  selectedTypes: string[]
  selectedElements: string[]
  selectedSetCodes: string[]
  selectedPackNames: string[]
  sortBy: string
  ownershipScope: string
  viewMode: OwnedCardsViewMode
  showCounts: boolean
  listPage: number
}

export interface OwnedCardsMainQueryState {
  accountId: string
  ownershipScope: string
  rarity: string[]
  cardType: string[]
  setCode: string[]
  packName: string[]
  element: string[]
  cardNameQuery: string
  sortBy: string
  page: number
  pageSize: number
}

interface OwnedCardDetailQueryState {
  lang: string
  ownershipScope: string
  pageSize: number
}

export interface OwnedCardExchangeAccountsQueryState {
  lang: string
  q: string
  sortBy: string
  sortOrder: 'asc' | 'desc'
  page: number
  pageSize: number
}

function normalizeOwnedQueryText(value: string): string {
  return value.trim()
}

function normalizeOwnedQueryList(values: readonly string[]): string[] {
  return values.map((item) => item.trim()).filter((item) => item.length > 0)
}

const OWNED_CARDS_QUERY_KEYS = {
  account: 'owned_account',
  q: 'owned_q',
  rarity: 'owned_rarity',
  type: 'owned_type',
  element: 'owned_element',
  set: 'owned_set',
  pack: 'owned_pack',
  sort: 'owned_sort',
  scope: 'owned_scope',
  view: 'owned_view',
  counts: 'owned_counts',
  page: 'owned_page'
} as const

function parseOwnedCardsListPage(searchParams: URLSearchParams): number {
  const value = Number(searchParams.get(OWNED_CARDS_QUERY_KEYS.page) ?? 0)
  return Number.isFinite(value) && value >= 0 ? value : 0
}

function normalizeOwnedCardsViewMode(value: string | null): OwnedCardsViewMode {
  return value === 'list' ? 'list' : 'grid'
}

function areStringArraysEqual(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

export function parseOwnedCardsSearchState(searchParams: URLSearchParams): OwnedCardsSearchState {
  return {
    accountQuery: searchParams.get(OWNED_CARDS_QUERY_KEYS.account) ?? '',
    cardNameQuery: searchParams.get(OWNED_CARDS_QUERY_KEYS.q) ?? '',
    selectedRarity: parseSearchList(searchParams, OWNED_CARDS_QUERY_KEYS.rarity),
    selectedTypes: parseSearchList(searchParams, OWNED_CARDS_QUERY_KEYS.type),
    selectedElements: parseSearchList(searchParams, OWNED_CARDS_QUERY_KEYS.element),
    selectedSetCodes: parseSearchList(searchParams, OWNED_CARDS_QUERY_KEYS.set),
    selectedPackNames: parseSearchList(searchParams, OWNED_CARDS_QUERY_KEYS.pack),
    sortBy: searchParams.get(OWNED_CARDS_QUERY_KEYS.sort) ?? 'acquired',
    ownershipScope: searchParams.get(OWNED_CARDS_QUERY_KEYS.scope) ?? 'owned',
    viewMode: normalizeOwnedCardsViewMode(searchParams.get(OWNED_CARDS_QUERY_KEYS.view)),
    showCounts: searchParams.get(OWNED_CARDS_QUERY_KEYS.counts) !== 'hide',
    listPage: parseOwnedCardsListPage(searchParams)
  }
}

export function areOwnedCardsSearchStatesEqual(
  left: OwnedCardsSearchState,
  right: OwnedCardsSearchState
): boolean {
  return left.accountQuery === right.accountQuery
    && left.cardNameQuery === right.cardNameQuery
    && areStringArraysEqual(left.selectedRarity, right.selectedRarity)
    && areStringArraysEqual(left.selectedTypes, right.selectedTypes)
    && areStringArraysEqual(left.selectedElements, right.selectedElements)
    && areStringArraysEqual(left.selectedSetCodes, right.selectedSetCodes)
    && areStringArraysEqual(left.selectedPackNames, right.selectedPackNames)
    && left.sortBy === right.sortBy
    && left.ownershipScope === right.ownershipScope
    && left.viewMode === right.viewMode
    && left.showCounts === right.showCounts
    && left.listPage === right.listPage
}

export function buildOwnedCardsSearchParams(
  state: OwnedCardsSearchState,
  baseParams: URLSearchParams
): URLSearchParams {
  const next = new URLSearchParams(baseParams)
  next.delete(OWNED_CARDS_QUERY_KEYS.rarity)
  next.delete(OWNED_CARDS_QUERY_KEYS.type)
  next.delete(OWNED_CARDS_QUERY_KEYS.element)
  next.delete(OWNED_CARDS_QUERY_KEYS.set)
  next.delete(OWNED_CARDS_QUERY_KEYS.pack)
  next.delete(OWNED_CARDS_QUERY_KEYS.account)
  next.delete(OWNED_CARDS_QUERY_KEYS.q)
  next.delete(OWNED_CARDS_QUERY_KEYS.sort)
  next.delete(OWNED_CARDS_QUERY_KEYS.scope)
  next.delete(OWNED_CARDS_QUERY_KEYS.view)
  next.delete(OWNED_CARDS_QUERY_KEYS.counts)
  next.delete(OWNED_CARDS_QUERY_KEYS.page)
  state.selectedRarity.forEach((item) => next.append(OWNED_CARDS_QUERY_KEYS.rarity, item))
  state.selectedTypes.forEach((item) => next.append(OWNED_CARDS_QUERY_KEYS.type, item))
  state.selectedElements.forEach((item) => next.append(OWNED_CARDS_QUERY_KEYS.element, item))
  state.selectedSetCodes.forEach((item) => next.append(OWNED_CARDS_QUERY_KEYS.set, item))
  state.selectedPackNames.forEach((item) => next.append(OWNED_CARDS_QUERY_KEYS.pack, item))
  next.set(OWNED_CARDS_QUERY_KEYS.account, state.accountQuery)
  if (state.cardNameQuery.trim()) {
    next.set(OWNED_CARDS_QUERY_KEYS.q, state.cardNameQuery.trim())
  }
  next.set(OWNED_CARDS_QUERY_KEYS.sort, state.sortBy)
  next.set(OWNED_CARDS_QUERY_KEYS.scope, state.ownershipScope)
  next.set(OWNED_CARDS_QUERY_KEYS.view, state.viewMode)
  next.set(OWNED_CARDS_QUERY_KEYS.counts, state.showCounts ? 'show' : 'hide')
  if (state.viewMode === 'list') {
    next.set(OWNED_CARDS_QUERY_KEYS.page, String(state.listPage))
  }
  return next
}

export function buildOwnedCardsListQueryParams(
  state: OwnedCardsMainQueryState
): Record<string, string | number | string[]> {
  return {
    account_id: normalizeOwnedQueryText(state.accountId),
    ownership_scope: state.ownershipScope,
    rarity: normalizeOwnedQueryList(state.rarity),
    card_type: normalizeOwnedQueryList(state.cardType),
    set_code: normalizeOwnedQueryList(state.setCode),
    pack_name: normalizeOwnedQueryList(state.packName),
    element: normalizeOwnedQueryList(state.element),
    q: normalizeOwnedQueryText(state.cardNameQuery),
    sort_by: state.sortBy,
    page: state.page,
    page_size: state.pageSize
  }
}

export function buildOwnedCardsStatsQueryParams(
  state: OwnedCardsMainQueryState
): Record<string, string | string[]> {
  return {
    account_id: normalizeOwnedQueryText(state.accountId),
    ownership_scope: state.ownershipScope,
    rarity: normalizeOwnedQueryList(state.rarity),
    card_type: normalizeOwnedQueryList(state.cardType),
    set_code: normalizeOwnedQueryList(state.setCode),
    pack_name: normalizeOwnedQueryList(state.packName),
    element: normalizeOwnedQueryList(state.element),
    q: normalizeOwnedQueryText(state.cardNameQuery)
  }
}

export function buildOwnedCardDetailQueryParams(
  state: OwnedCardDetailQueryState
): Record<string, string | number> {
  return {
    lang: state.lang,
    ownership_scope: state.ownershipScope,
    page_size: state.pageSize
  }
}

export function buildOwnedCardExchangeAccountsQueryParams(
  state: OwnedCardExchangeAccountsQueryState
): Record<string, string | number> {
  return {
    lang: state.lang,
    q: normalizeOwnedQueryText(state.q),
    sort_by: state.sortBy,
    sort_order: state.sortOrder,
    page: state.page,
    page_size: state.pageSize
  }
}
