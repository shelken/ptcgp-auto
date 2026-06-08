import { parseSearchList } from '../lib/list-utils'

export type RecordsViewMode = 'grid' | 'list'

interface RecordsSearchState {
  selectedRarity: string[]
  selectedTypes: string[]
  selectedSetCodes: string[]
  cardNameQuery: string
  viewMode: RecordsViewMode
}

interface RecordsApiBaseQueryParamsInput {
  lang: string
  pageSize: number
  selectedRarity: string[]
  selectedTypes: string[]
  selectedSetCodes: string[]
  cardNameQuery: string
}

interface RecordsApiQueryParamsInput extends RecordsApiBaseQueryParamsInput {
  page: number
}

const RECORDS_QUERY_KEYS = {
  rarity: 'records_rarity',
  type: 'records_type',
  set: 'records_set',
  q: 'records_q',
  view: 'records_view'
} as const

function normalizeRecordsViewMode(
  raw: string | null | undefined,
  fallbackView: RecordsViewMode
): RecordsViewMode {
  return raw === 'list' || raw === 'grid' ? raw : fallbackView
}

export function parseRecordsSearchState(
  searchParams: URLSearchParams,
  options: {
    fallbackView?: RecordsViewMode
  } = {}
): RecordsSearchState {
  const fallbackView = options.fallbackView ?? 'grid'
  return {
    selectedRarity: parseSearchList(searchParams, RECORDS_QUERY_KEYS.rarity),
    selectedTypes: parseSearchList(searchParams, RECORDS_QUERY_KEYS.type),
    selectedSetCodes: parseSearchList(searchParams, RECORDS_QUERY_KEYS.set),
    cardNameQuery: searchParams.get(RECORDS_QUERY_KEYS.q) ?? '',
    viewMode: normalizeRecordsViewMode(
      searchParams.get(RECORDS_QUERY_KEYS.view),
      fallbackView
    )
  }
}

function areStringArraysEqual(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

export function areRecordsSearchStatesEqual(
  left: RecordsSearchState,
  right: RecordsSearchState
): boolean {
  return areStringArraysEqual(left.selectedRarity, right.selectedRarity)
    && areStringArraysEqual(left.selectedTypes, right.selectedTypes)
    && areStringArraysEqual(left.selectedSetCodes, right.selectedSetCodes)
    && left.cardNameQuery === right.cardNameQuery
    && left.viewMode === right.viewMode
}

export function buildRecordsSearchParams(
  state: RecordsSearchState,
  baseParams: URLSearchParams
): URLSearchParams {
  const next = new URLSearchParams(baseParams)
  next.delete(RECORDS_QUERY_KEYS.rarity)
  next.delete(RECORDS_QUERY_KEYS.type)
  next.delete(RECORDS_QUERY_KEYS.set)
  next.delete(RECORDS_QUERY_KEYS.q)
  next.delete(RECORDS_QUERY_KEYS.view)
  state.selectedRarity.forEach((item) => next.append(RECORDS_QUERY_KEYS.rarity, item))
  state.selectedTypes.forEach((item) => next.append(RECORDS_QUERY_KEYS.type, item))
  state.selectedSetCodes.forEach((item) => next.append(RECORDS_QUERY_KEYS.set, item))
  if (state.cardNameQuery.trim()) {
    next.set(RECORDS_QUERY_KEYS.q, state.cardNameQuery.trim())
  }
  next.set(RECORDS_QUERY_KEYS.view, state.viewMode)
  return next
}

function buildRecordsApiBaseQueryParams(
  input: RecordsApiBaseQueryParamsInput
): Record<string, string | number | Array<string>> {
  return {
    lang: input.lang,
    page_size: input.pageSize,
    rarity: input.selectedRarity,
    card_type: input.selectedTypes,
    set_code: input.selectedSetCodes,
    q: input.cardNameQuery.trim()
  }
}

export function buildRecordsApiQueryParams(
  input: RecordsApiQueryParamsInput
): Record<string, string | number | Array<string>> {
  return {
    ...buildRecordsApiBaseQueryParams(input),
    page: input.page
  }
}
