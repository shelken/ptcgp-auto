import { useCallback, useEffect, useMemo } from 'react'

import { usePersistedState } from '../../hooks/use-persisted-state'

import type {
  ManagementListDynamicOptions,
  ManagementListSortOrder,
  ManagementListSpec,
  ManagementListState
} from './list-spec'
import {
  applyManagementListSortClick,
  type PersistedManagementListState,
  normalizeManagementListRuntimeState,
  normalizeManagementListState
} from './list-state-utils'

const MANAGEMENT_STATE_STORAGE_PREFIX = 'ptcgp_management_state:'

function managementListStateKey(storageKey: string): string {
  return `${MANAGEMENT_STATE_STORAGE_PREFIX}${storageKey}:list_state`
}

function isSameState(left: ManagementListState, right: ManagementListState): boolean {
  if (
    left.page !== right.page
    || left.pageSize !== right.pageSize
    || left.sortBy !== right.sortBy
    || left.sortOrder !== right.sortOrder
  ) {
    return false
  }
  const leftKeys = Object.keys(left.filters)
  const rightKeys = Object.keys(right.filters)
  if (leftKeys.length !== rightKeys.length) {
    return false
  }
  return leftKeys.every((key) => left.filters[key] === right.filters[key])
}

export function useManagementListState(
  spec: ManagementListSpec,
  runtime?: {
    dynamicOptions?: ManagementListDynamicOptions
    sortOptions?: readonly { value: string }[]
  }
) {
  const [persistedState, setPersistedState] = usePersistedState<PersistedManagementListState>(
    managementListStateKey(spec.storageKey),
    {}
  )
  const baseState = useMemo(
    () => normalizeManagementListState(spec, persistedState, runtime?.sortOptions),
    [persistedState, runtime?.sortOptions, spec]
  )
  const state = useMemo(
    () => normalizeManagementListRuntimeState(spec, baseState, runtime),
    [baseState, runtime, spec]
  )

  useEffect(() => {
    if (isSameState(baseState, state)) {
      return
    }
    setPersistedState(state)
  }, [baseState, setPersistedState, state])

  const normalizeState = useCallback((rawState: ManagementListState) => {
    const normalizedState = normalizeManagementListState(spec, rawState, runtime?.sortOptions)
    return normalizeManagementListRuntimeState(spec, normalizedState, runtime)
  }, [runtime, spec])

  const commitState = useCallback((nextState: ManagementListState) => {
    setPersistedState(nextState)
  }, [setPersistedState])

  const setFilter = useCallback((key: string, value: string) => {
    const nextState = normalizeState({
      ...state,
      page: 0,
      filters: {
        ...state.filters,
        [key]: value
      }
    })
    commitState(nextState)
  }, [commitState, normalizeState, state])

  const setFilters = useCallback((filters: Record<string, string>) => {
    const nextState = normalizeState({
      ...state,
      page: 0,
      filters: {
        ...state.filters,
        ...filters
      }
    })
    commitState(nextState)
  }, [commitState, normalizeState, state])

  const setSort = useCallback((sortBy: string, sortOrder?: ManagementListSortOrder) => {
    const nextState = normalizeState({
      ...state,
      page: 0,
      sortBy,
      sortOrder: sortOrder ?? state.sortOrder
    })
    commitState(nextState)
  }, [commitState, normalizeState, state])

  const cycleSort = useCallback((sortBy: string) => {
    const nextState = normalizeState(applyManagementListSortClick(spec, state, sortBy, runtime?.sortOptions))
    commitState(nextState)
  }, [commitState, normalizeState, runtime?.sortOptions, spec, state])

  const setPage = useCallback((page: number) => {
    const nextState = normalizeState({
      ...state,
      page
    })
    commitState(nextState)
  }, [commitState, normalizeState, state])

  const setPageSize = useCallback((pageSize: number) => {
    const nextState = normalizeState({
      ...state,
      page: 0,
      pageSize
    })
    commitState(nextState)
  }, [commitState, normalizeState, state])

  const resetPage = useCallback(() => {
    if (state.page === 0) {
      return
    }
    commitState({
      ...state,
      page: 0
    })
  }, [commitState, state])

  return {
    state,
    setFilter,
    setFilters,
    setSort,
    cycleSort,
    setPage,
    setPageSize,
    resetPage
  }
}
