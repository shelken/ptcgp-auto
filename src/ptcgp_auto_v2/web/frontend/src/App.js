import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from 'react';
import { Navigate, NavLink, Route, Routes, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useBootstrap } from '@/hooks/use-bootstrap';
import { ManagementPage } from '@/pages/management-page';
import { OwnedCardsPage } from '@/pages/owned-cards-page';
import { RecordsPage } from '@/pages/records-page';
function setLangParam(nextLang, searchParams, setSearchParams) {
    const next = new URLSearchParams(searchParams);
    next.set('lang', nextLang);
    setSearchParams(next);
}
export default function App() {
    const [searchParams, setSearchParams] = useSearchParams();
    const lang = searchParams.get('lang') ?? 'zh_CN';
    const bootstrap = useBootstrap(lang);
    const t = bootstrap.data?.t ?? {};
    useEffect(() => {
        // 迁移过渡期继续复用旧版事件绑定逻辑，避免局部交互回归。
        const scriptId = 'legacy-web-main';
        if (document.getElementById(scriptId)) {
            return;
        }
        const script = document.createElement('script');
        script.id = scriptId;
        script.type = 'module';
        script.src = '/static/js/main.js';
        document.body.appendChild(script);
    }, []);
    if (bootstrap.isLoading) {
        return (_jsx("main", { className: "mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center p-4", children: _jsx("div", { className: "brutal-card p-4 text-sm text-muted", children: "\u52A0\u8F7D\u4E2D..." }) }));
    }
    if (bootstrap.isError || !bootstrap.data) {
        return (_jsx("main", { className: "mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center p-4", children: _jsx("div", { className: "brutal-card p-4 text-sm text-red-600", children: bootstrap.error.message }) }));
    }
    return (_jsxs("main", { className: "mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 p-4", children: [_jsxs("header", { className: "flex flex-wrap items-center justify-between gap-3", children: [_jsx("h1", { className: "text-xl font-bold tracking-widest", children: t.app_title ?? 'PTCGP Auto Web' }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Button, { type: "button", size: "sm", variant: lang === 'en' ? 'default' : 'outline', onClick: () => setLangParam('en', searchParams, setSearchParams), children: "EN" }), _jsx(Button, { type: "button", size: "sm", variant: lang === 'zh_CN' ? 'default' : 'outline', onClick: () => setLangParam('zh_CN', searchParams, setSearchParams), children: "\u4E2D\u6587" })] })] }), _jsxs("nav", { className: "flex flex-wrap gap-2 brutal-card p-4", children: [_jsx(NavLink, { to: "/records", children: ({ isActive }) => (_jsx(Button, { size: "sm", variant: isActive ? 'default' : 'outline', type: "button", children: t.tab_records ?? 'RECORDS' })) }), _jsx(NavLink, { to: "/owned-cards", children: ({ isActive }) => (_jsx(Button, { size: "sm", variant: isActive ? 'default' : 'outline', type: "button", children: t.tab_owned_cards ?? 'OWNED CARDS' })) }), _jsx(NavLink, { to: "/management", children: ({ isActive }) => (_jsx(Button, { size: "sm", variant: isActive ? 'default' : 'outline', type: "button", children: t.tab_management ?? 'MANAGEMENT' })) })] }), _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/records", replace: true }) }), _jsx(Route, { path: "/records", element: _jsx(RecordsPage, { lang: lang, options: bootstrap.data.options, t: t }) }), _jsx(Route, { path: "/owned-cards", element: _jsx(OwnedCardsPage, { lang: lang, options: bootstrap.data.options, t: t }) }), _jsx(Route, { path: "/management/*", element: _jsx(ManagementPage, { lang: lang, t: t }) })] })] }));
}
