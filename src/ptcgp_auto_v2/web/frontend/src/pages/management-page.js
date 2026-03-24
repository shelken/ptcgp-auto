import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { HtmlFragment } from '@/components/html-fragment';
import { Button } from '@/components/ui/button';
const sections = [
    { key: 'accounts', endpoint: '/management/accounts', labelKey: 'menu_accounts', fallback: 'Accounts' },
    { key: 'plans', endpoint: '/management/plans', labelKey: 'menu_plans', fallback: 'Plans' },
    { key: 'resources', endpoint: '/management/resources', labelKey: 'menu_resources', fallback: 'Resources' },
    { key: 'tasks', endpoint: '/management/tasks', labelKey: 'menu_tasks', fallback: 'Tasks' },
    { key: 'metadata', endpoint: '/management/metadata', labelKey: 'menu_metadata', fallback: 'Metadata' },
    { key: 'daily-gift', endpoint: '/management/daily-gift', labelKey: 'menu_daily_gift', fallback: 'Daily Gift' },
    { key: 'friendships', endpoint: '/management/friendships', labelKey: 'menu_friendships', fallback: 'Friendships' },
    { key: 'exchange-cards', endpoint: '/management/exchange-cards', labelKey: 'menu_exchange_cards', fallback: 'Exchange Cards' },
    { key: 'notifications', endpoint: '/management/notifications', labelKey: 'menu_notifications', fallback: 'Notifications' }
];
function ManagementSection({ lang, endpoint, keyName }) {
    const url = useMemo(() => `${endpoint}?lang=${encodeURIComponent(lang)}`, [endpoint, lang]);
    return _jsx(HtmlFragment, { url: url, queryKey: ['management', keyName, lang] });
}
export function ManagementPage({ lang, t }) {
    return (_jsxs("section", { className: "space-y-4", children: [_jsx("div", { className: "flex flex-wrap gap-2 brutal-card p-4", children: sections.map((section) => (_jsx(NavLink, { to: section.key, children: ({ isActive }) => (_jsx(Button, { variant: isActive ? 'default' : 'outline', size: "sm", type: "button", children: t[section.labelKey] ?? section.fallback })) }, section.key))) }), _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "accounts", replace: true }) }), sections.map((section) => (_jsx(Route, { path: section.key, element: _jsx(ManagementSection, { lang: lang, endpoint: section.endpoint, keyName: section.key }) }, section.key)))] })] }));
}
