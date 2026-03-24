import { useQuery } from '@tanstack/react-query';
import { fetchJson } from '@/lib/api';
export function useBootstrap(lang) {
    return useQuery({
        queryKey: ['bootstrap', lang],
        queryFn: () => fetchJson(`/api/react/bootstrap?lang=${encodeURIComponent(lang)}`),
        staleTime: 60_000
    });
}
