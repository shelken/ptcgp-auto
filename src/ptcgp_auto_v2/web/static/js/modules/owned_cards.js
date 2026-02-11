const STORAGE_KEY_OWNED_COLS = 'ptcgp_owned_cols';

// --- 设置已拥有卡牌网格列数 ---
export function setOwnedGridCols(value) {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    const cols = parseInt(value, 10);
    if (Number.isNaN(cols)) return;

    container.style.setProperty('--owned-grid-cols', cols);
    const label = document.getElementById('owned-cols-value');
    if (label) label.textContent = cols;
    localStorage.setItem(STORAGE_KEY_OWNED_COLS, String(cols));

    document.querySelectorAll('.owned-cols-btn').forEach((button) => {
        const target = parseInt(button.dataset.cols, 10);
        if (target === cols) {
            button.classList.add('active');
            button.setAttribute('aria-pressed', 'true');
        } else {
            button.classList.remove('active');
            button.setAttribute('aria-pressed', 'false');
        }
    });
}

// --- 切换数量显示 ---
export function toggleOwnedCounts() {
    const container = document.getElementById('owned-cards-container');
    if (!container) return;
    container.classList.toggle('show-counts');

    const btn = document.getElementById('owned-counts-toggle');
    if (!btn) return;
    const showText = btn.dataset.showText || btn.textContent;
    const hideText = btn.dataset.hideText || btn.textContent;
    if (container.classList.contains('show-counts')) {
        btn.textContent = hideText;
    } else {
        btn.textContent = showText;
    }
}

// --- 恢复网格列数 ---
export function restoreOwnedGridCols() {
    const stored = localStorage.getItem(STORAGE_KEY_OWNED_COLS);
    const value = stored || '5';
    setOwnedGridCols(value);
}
