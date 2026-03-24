import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { HtmlFragment } from '@/components/html-fragment';
function appendArrayParams(params, key, values) {
    values.forEach((value) => {
        params.append(key, value);
    });
}
export function RecordsPage({ lang, options, t }) {
    const [selectedRarity, setSelectedRarity] = useState([]);
    const [selectedTypes, setSelectedTypes] = useState([]);
    const url = useMemo(() => {
        const params = new URLSearchParams();
        params.set('page', '0');
        params.set('page_size', '10');
        params.set('lang', lang);
        appendArrayParams(params, 'rarity', selectedRarity);
        appendArrayParams(params, 'card_type', selectedTypes);
        return `/api/records?${params.toString()}`;
    }, [lang, selectedRarity, selectedTypes]);
    function toggleItem(current, value) {
        if (current.includes(value)) {
            return current.filter((item) => item !== value);
        }
        return [...current, value];
    }
    return (_jsxs("section", { className: "space-y-4", children: [_jsxs("div", { className: "brutal-card p-4 space-y-4", children: [_jsx("h2", { className: "font-bold tracking-widest uppercase text-sm", children: t.filter_title ?? 'Filters' }), _jsxs("div", { className: "space-y-2", children: [_jsx("div", { className: "text-xs text-muted uppercase tracking-widest", children: t.filter_rarity ?? 'Rarity' }), _jsx("div", { className: "flex flex-wrap gap-2", children: options.rarities.map((rarity) => (_jsx(Button, { type: "button", size: "sm", variant: selectedRarity.includes(rarity) ? 'default' : 'outline', onClick: () => setSelectedRarity((prev) => toggleItem(prev, rarity)), children: t[`rarity_${rarity}`] ?? rarity }, rarity))) })] }), _jsxs("div", { className: "space-y-2", children: [_jsx("div", { className: "text-xs text-muted uppercase tracking-widest", children: t.filter_type ?? 'Type' }), _jsx("div", { className: "flex flex-wrap gap-2", children: options.card_types.map((cardType) => (_jsx(Button, { type: "button", size: "sm", variant: selectedTypes.includes(cardType) ? 'default' : 'outline', onClick: () => setSelectedTypes((prev) => toggleItem(prev, cardType)), children: t[`type_${cardType}`] ?? cardType }, cardType))) })] })] }), _jsx(HtmlFragment, { url: url, queryKey: ['records', lang, selectedRarity.join(','), selectedTypes.join(',')], className: "space-y-2" })] }));
}
