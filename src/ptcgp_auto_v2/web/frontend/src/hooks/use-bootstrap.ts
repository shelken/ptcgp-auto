import { useQuery } from '@tanstack/react-query'

import { fetchJson } from '@/lib/api'
import type { BootstrapResponse } from '@/types/api'

export function useBootstrap(lang: string) {
  return useQuery({
    queryKey: ['bootstrap', lang],
    queryFn: () => fetchJson<BootstrapResponse>(`/api/react/bootstrap?lang=${encodeURIComponent(lang)}`),
    staleTime: 60_000
  })
}
