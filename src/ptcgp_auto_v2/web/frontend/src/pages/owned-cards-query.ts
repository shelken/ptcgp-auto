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
