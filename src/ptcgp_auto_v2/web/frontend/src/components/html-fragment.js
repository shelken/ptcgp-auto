import { jsx as _jsx } from "react/jsx-runtime";
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef } from 'react';
import { fetchText } from '@/lib/api';
export function HtmlFragment({ url, queryKey, className, loadingText = '加载中...', emptyText = '暂无内容' }) {
    const containerRef = useRef(null);
    const stableUrl = useMemo(() => url, [url]);
    const query = useQuery({
        queryKey: [...queryKey, stableUrl],
        queryFn: () => fetchText(stableUrl),
        staleTime: 5_000
    });
    useEffect(() => {
        if (!query.data || !containerRef.current) {
            return;
        }
        containerRef.current.innerHTML = query.data;
        if (window.htmx) {
            window.htmx.process(containerRef.current);
        }
    }, [query.data]);
    if (query.isLoading) {
        return _jsx("div", { className: "brutal-card p-4 text-sm text-muted", children: loadingText });
    }
    if (query.isError) {
        return (_jsx("div", { className: "brutal-card p-4 text-sm text-red-600", children: query.error.message }));
    }
    if (!query.data?.trim()) {
        return _jsx("div", { className: "brutal-card p-4 text-sm text-muted", children: emptyText });
    }
    return _jsx("div", { ref: containerRef, className: className });
}
