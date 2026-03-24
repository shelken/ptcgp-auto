import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { HtmlFragment } from '@/components/html-fragment';
function toggleItems(current, value) {
    if (current.includes(value)) {
        return current.filter((item) => item !== value);
    }
    return [...current, value];
}
function appendArray(params, key, values) {
    values.forEach((value) => params.append(key, value));
}
export function OwnedCardsPage({ lang, options, t }) {
    const [selectedRarity, setSelectedRarity] = useState([]);
    const [selectedTypes, setSelectedTypes] = useState([]);
    const [selectedElements, setSelectedElements] = useState([]);
    const [selectedSetCodes, setSelectedSetCodes] = useState([]);
    const [selectedPackNames, setSelectedPackNames] = useState([]);
    const [sortBy, setSortBy] = useState('acquired');
    const [ownershipScope, setOwnershipScope] = useState('owned');
    const queryUrl = useMemo(() => {
        const params = new URLSearchParams();
        params.set('page', '0');
        params.set('page_size', '60');
        params.set('lang', lang);
        params.set('sort_by', sortBy);
        params.set('ownership_scope', ownershipScope);
        appendArray(params, 'rarity', selectedRarity);
        appendArray(params, 'card_type', selectedTypes);
        appendArray(params, 'element', selectedElements);
        appendArray(params, 'set_code', selectedSetCodes);
        appendArray(params, 'pack_name', selectedPackNames);
        return `/api/owned-cards?${params.toString()}`;
    }, [
        lang,
        ownershipScope,
        selectedElements,
        selectedPackNames,
        selectedRarity,
        selectedSetCodes,
        selectedTypes,
        sortBy
    ]);
    const statsUrl = useMemo(() => {
        const params = new URLSearchParams();
        params.set('lang', lang);
        params.set('ownership_scope', ownershipScope);
        appendArray(params, 'rarity', selectedRarity);
        appendArray(params, 'card_type', selectedTypes);
        appendArray(params, 'element', selectedElements);
        appendArray(params, 'set_code', selectedSetCodes);
        appendArray(params, 'pack_name', selectedPackNames);
        return `/api/owned-cards/stats?${params.toString()}`;
    }, [lang, ownershipScope, selectedElements, selectedPackNames, selectedRarity, selectedSetCodes, selectedTypes]);
    return (_jsxs("section", { className: "space-y-4", children: [_jsxs("div", { className: "brutal-card p-4 space-y-4", children: [_jsx("h2", { className: "font-bold tracking-widest uppercase text-sm", children: t.filter_title ?? 'Filters' }), _jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsx(Button, { type: "button", size: "sm", variant: ownershipScope === 'owned' ? 'default' : 'outline', onClick: () => setOwnershipScope('owned'), children: t.owned_scope_owned ?? 'Owned' }), _jsx(Button, { type: "button", size: "sm", variant: ownershipScope === 'missing' ? 'default' : 'outline', onClick: () => setOwnershipScope('missing'), children: t.owned_scope_missing ?? 'Missing' }), _jsx(Button, { type: "button", size: "sm", variant: ownershipScope === 'all' ? 'default' : 'outline', onClick: () => setOwnershipScope('all'), children: t.owned_scope_all ?? 'All' })] }), _jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsx(Button, { type: "button", size: "sm", variant: sortBy === 'acquired' ? 'default' : 'outline', onClick: () => setSortBy('acquired'), children: t.owned_sort_acquired ?? 'Acquired' }), _jsx(Button, { type: "button", size: "sm", variant: sortBy === 'rarity' ? 'default' : 'outline', onClick: () => setSortBy('rarity'), children: t.owned_sort_rarity ?? 'Rarity' }), _jsx(Button, { type: "button", size: "sm", variant: sortBy === 'count' ? 'default' : 'outline', onClick: () => setSortBy('count'), children: t.owned_sort_count ?? 'Count' })] }), _jsxs("details", { children: [_jsx("summary", { className: "cursor-pointer text-xs uppercase tracking-widest text-muted", children: t.filter_rarity ?? 'Rarity' }), _jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: options.rarities.map((rarity) => (_jsx(Button, { type: "button", size: "sm", variant: selectedRarity.includes(rarity) ? 'default' : 'outline', onClick: () => setSelectedRarity((prev) => toggleItems(prev, rarity)), children: t[`rarity_${rarity}`] ?? rarity }, rarity))) })] }), _jsxs("details", { children: [_jsx("summary", { className: "cursor-pointer text-xs uppercase tracking-widest text-muted", children: t.filter_type ?? 'Type' }), _jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: options.card_types.map((cardType) => (_jsx(Button, { type: "button", size: "sm", variant: selectedTypes.includes(cardType) ? 'default' : 'outline', onClick: () => setSelectedTypes((prev) => toggleItems(prev, cardType)), children: t[`type_${cardType}`] ?? cardType }, cardType))) })] }), _jsxs("details", { children: [_jsx("summary", { className: "cursor-pointer text-xs uppercase tracking-widest text-muted", children: t.filter_set ?? 'Set' }), _jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: options.card_sets.map((item) => (_jsx(Button, { type: "button", size: "sm", variant: selectedSetCodes.includes(item.code) ? 'default' : 'outline', onClick: () => setSelectedSetCodes((prev) => toggleItems(prev, item.code)), children: item.display_name }, item.code))) })] }), _jsxs("details", { children: [_jsx("summary", { className: "cursor-pointer text-xs uppercase tracking-widest text-muted", children: t.filter_pack ?? 'Pack' }), _jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: options.packs.map((item) => (_jsx(Button, { type: "button", size: "sm", variant: selectedPackNames.includes(item.name) ? 'default' : 'outline', onClick: () => setSelectedPackNames((prev) => toggleItems(prev, item.name)), children: item.display_name }, item.name))) })] }), _jsxs("details", { children: [_jsx("summary", { className: "cursor-pointer text-xs uppercase tracking-widest text-muted", children: t.filter_element ?? 'Element' }), _jsx("div", { className: "mt-2 flex flex-wrap gap-2", children: options.elements.map((item) => (_jsx(Button, { type: "button", size: "sm", variant: selectedElements.includes(item) ? 'default' : 'outline', onClick: () => setSelectedElements((prev) => toggleItems(prev, item)), children: t[`element_${item}`] ?? item }, item))) })] })] }), _jsx(HtmlFragment, { url: statsUrl, queryKey: ['owned-stats', lang, ownershipScope, sortBy, selectedRarity.join(','), selectedTypes.join(','), selectedSetCodes.join(','), selectedPackNames.join(','), selectedElements.join(',')] }), _jsx(HtmlFragment, { url: queryUrl, queryKey: ['owned-list', lang, ownershipScope, sortBy, selectedRarity.join(','), selectedTypes.join(','), selectedSetCodes.join(','), selectedPackNames.join(','), selectedElements.join(',')] })] }));
}
