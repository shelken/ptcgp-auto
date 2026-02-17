// --- 相对时间文本 ---
function getRelativeLabels(container) {
    return {
        locale: container.dataset.relativeLocale || 'en',
        justNow: container.dataset.relativeJustNow || 'just now',
        soon: container.dataset.relativeSoon || 'soon',
        minutes: container.dataset.relativeMinutes || 'min',
        hours: container.dataset.relativeHours || 'hr',
        days: container.dataset.relativeDays || 'day',
        ago: container.dataset.relativeAgo || 'ago',
        in: container.dataset.relativeIn || 'in'
    };
}

// --- 格式化相对时间 ---
function formatRelativeTime(target, labels) {
    const diffMs = target.getTime() - Date.now();
    const future = diffMs > 0;
    const absSec = Math.abs(diffMs) / 1000;

    if (absSec < 60) {
        return future ? labels.soon : labels.justNow;
    }

    let value = 0;
    let unit = labels.minutes;
    if (absSec < 3600) {
        value = Math.round(absSec / 60);
        unit = labels.minutes;
    } else if (absSec < 86400) {
        value = Math.round(absSec / 3600);
        unit = labels.hours;
    } else {
        value = Math.round(absSec / 86400);
        unit = labels.days;
    }

    if (labels.locale.startsWith('en')) {
        return future ? `${labels.in} ${value} ${unit}` : `${value} ${unit} ${labels.ago}`;
    }

    return `${value}${unit}${future ? labels.in : labels.ago}`;
}

// --- 更新相对时间 ---
export function updateRelativeTimes(root = document) {
    const containers = [];
    if (root && root.nodeType === 1 && root.matches && root.matches('[data-relative-locale]')) {
        containers.push(root);
    }
    if (root && root.nodeType === 1 && root.closest) {
        const closestContainer = root.closest('[data-relative-locale]');
        if (closestContainer && !containers.includes(closestContainer)) {
            containers.push(closestContainer);
        }
    }
    if (root && root.querySelectorAll) {
        containers.push(...root.querySelectorAll('[data-relative-locale]'));
    }
    containers.forEach((container) => {
        const labels = getRelativeLabels(container);
        container.querySelectorAll('.relative-time').forEach((el) => {
            const iso = el.dataset.iso;
            if (!iso) return;
            const date = new Date(iso);
            if (Number.isNaN(date.getTime())) return;
            el.textContent = formatRelativeTime(date, labels);
            if (el.dataset.tooltip) {
                el.setAttribute('data-tooltip', el.dataset.tooltip);
            }
        });
    });
}
