const TOOLTIP_SELECTOR = '.tooltip-tag[data-tooltip], .tooltip-text[data-tooltip]';
const TOOLTIP_OFFSET = 24;
const TOOLTIP_VIEWPORT_GAP = 8;

const tooltipState = {
    activeElement: null,
    layer: null,
};

function ensureTooltipLayer() {
    if (tooltipState.layer instanceof HTMLElement) {
        return tooltipState.layer;
    }

    const layer = document.createElement('div');
    layer.id = 'app-tooltip-layer';
    layer.setAttribute('role', 'tooltip');
    layer.setAttribute('aria-hidden', 'true');
    document.body.appendChild(layer);
    document.body.classList.add('tooltip-layer-enabled');
    tooltipState.layer = layer;
    return layer;
}

function resolveTooltipElement(target) {
    if (!(target instanceof Element)) {
        return null;
    }
    return target.closest(TOOLTIP_SELECTOR);
}

function resolvePlacement(element) {
    if (!(element instanceof HTMLElement)) {
        return 'top';
    }
    return element.classList.contains('tooltip-text--left') ? 'left' : 'top';
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function positionTooltip() {
    const element = tooltipState.activeElement;
    const layer = tooltipState.layer;
    if (!(element instanceof HTMLElement) || !(layer instanceof HTMLElement)) {
        return;
    }

    const placement = resolvePlacement(element);
    const rect = element.getBoundingClientRect();
    const layerRect = layer.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let left = rect.left + (rect.width / 2) - (layerRect.width / 2);
    let top = rect.top - layerRect.height - TOOLTIP_OFFSET;

    if (placement === 'left') {
        left = rect.left - layerRect.width - TOOLTIP_OFFSET;
        top = rect.top + (rect.height / 2) - (layerRect.height / 2);
    }

    left = clamp(left, TOOLTIP_VIEWPORT_GAP, viewportWidth - layerRect.width - TOOLTIP_VIEWPORT_GAP);
    top = clamp(top, TOOLTIP_VIEWPORT_GAP, viewportHeight - layerRect.height - TOOLTIP_VIEWPORT_GAP);

    layer.dataset.placement = placement;
    layer.style.left = `${Math.round(left)}px`;
    layer.style.top = `${Math.round(top)}px`;
}

function showTooltip(element) {
    if (!(element instanceof HTMLElement)) {
        return;
    }

    const tooltipText = element.dataset.tooltip;
    if (!tooltipText) {
        hideTooltip();
        return;
    }

    const layer = ensureTooltipLayer();
    tooltipState.activeElement = element;
    layer.textContent = tooltipText;
    layer.dataset.visible = 'true';
    layer.setAttribute('aria-hidden', 'false');
    positionTooltip();
}

function hideTooltip() {
    if (!(tooltipState.layer instanceof HTMLElement)) {
        tooltipState.activeElement = null;
        return;
    }

    tooltipState.activeElement = null;
    tooltipState.layer.dataset.visible = 'false';
    tooltipState.layer.setAttribute('aria-hidden', 'true');
}

function handlePointerOver(event) {
    const target = resolveTooltipElement(event.target);
    if (!target) {
        return;
    }
    if (tooltipState.activeElement === target) {
        return;
    }
    showTooltip(target);
}

function handlePointerOut(event) {
    const target = resolveTooltipElement(event.target);
    if (!target || tooltipState.activeElement !== target) {
        return;
    }

    const related = event.relatedTarget;
    if (related instanceof Node && target.contains(related)) {
        return;
    }
    hideTooltip();
}

function handleFocusIn(event) {
    const target = resolveTooltipElement(event.target);
    if (!target) {
        return;
    }
    showTooltip(target);
}

function handleFocusOut(event) {
    const target = resolveTooltipElement(event.target);
    if (!target || tooltipState.activeElement !== target) {
        return;
    }
    hideTooltip();
}

export function initTooltipLayer() {
    if (window.__tooltipLayerBound) {
        return;
    }

    window.__tooltipLayerBound = true;
    ensureTooltipLayer();

    document.body.addEventListener('mouseover', handlePointerOver);
    document.body.addEventListener('mouseout', handlePointerOut);
    document.body.addEventListener('focusin', handleFocusIn);
    document.body.addEventListener('focusout', handleFocusOut);

    window.addEventListener('scroll', positionTooltip, { passive: true });
    window.addEventListener('resize', positionTooltip);
    document.addEventListener('modal:closed', hideTooltip);
    document.addEventListener('htmx:beforeSwap', hideTooltip);
}
