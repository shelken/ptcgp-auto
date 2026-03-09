/**
 * 主题管理模块
 * 支持模式：auto/light/dark/manual
 * auto时：亮色默认野兽派，暗色默认复古未来
 */

const STORAGE_KEY_THEME = 'ptcgp_theme';
const STORAGE_KEY_THEME_MODE = 'ptcgp_theme_mode';
const STORAGE_KEY_LAST_LIGHT = 'ptcgp_last_light_theme';
const STORAGE_KEY_LAST_DARK = 'ptcgp_last_dark_theme';

const LIGHT_THEMES = ['brutalist', 'organic', 'playful', 'editorial', 'pastel'];
const DARK_THEMES = ['retro', 'art_deco', 'luxury'];
const DEFAULT_LIGHT_THEME = 'brutalist';
const DEFAULT_DARK_THEME = 'retro';

const MODE_CYCLE = ['auto', 'light', 'dark'];
const THEME_FONT_LINK_PREFIX = 'theme-font-';

// 主题字体按需加载映射：基础字体 Space Grotesk / Space Mono 已在 index.html 固定加载
const THEME_FONT_STYLESHEET = {
    organic: 'https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&display=swap',
    luxury: 'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap',
    playful: 'https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap',
    editorial: 'https://fonts.googleapis.com/css2?family=Bodoni+Moda:wght@400;700&display=swap',
    art_deco: 'https://fonts.googleapis.com/css2?family=Limelight&display=swap',
    pastel: 'https://fonts.googleapis.com/css2?family=Quicksand:wght@400;700&display=swap',
};

// SVG 图标定义
const SVG_ICONS = {
  // 自动模式：太阳+月亮组合
  auto: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/><path d="M12 3a9 9 0 1 0 9 9" opacity="0.5"/></svg>`,
  // 亮色模式：太阳
  light: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`,
  // 暗色模式：月亮
  dark: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  // 手动模式：调色盘
  manual: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>`
};

/**
 * 获取当前模式
 */
export function getThemeMode() {
    return localStorage.getItem(STORAGE_KEY_THEME_MODE) || 'auto';
}

/**
 * 获取当前主题名
 */
export function getCurrentTheme() {
    return localStorage.getItem(STORAGE_KEY_THEME) || DEFAULT_LIGHT_THEME;
}

/**
 * 判断主题所属分组
 */
function getThemeGroup(theme) {
    if (LIGHT_THEMES.includes(theme)) return 'light';
    if (DARK_THEMES.includes(theme)) return 'dark';
    return 'light';
}

/**
 * 根据模式选择主题
 */
function resolveThemeByMode(mode) {
    const storedTheme = getCurrentTheme();
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    switch (mode) {
        case 'auto':
            // auto时：亮色=野兽派，暗色=复古未来
            return systemPrefersDark ? DEFAULT_DARK_THEME : DEFAULT_LIGHT_THEME;
        
        case 'light':
            // light模式：优先用该组上次记忆，否则野兽派
            const lastLight = localStorage.getItem(STORAGE_KEY_LAST_LIGHT);
            return LIGHT_THEMES.includes(lastLight) ? lastLight : DEFAULT_LIGHT_THEME;
        
        case 'dark':
            // dark模式：优先用该组上次记忆，否则复古未来
            const lastDark = localStorage.getItem(STORAGE_KEY_LAST_DARK);
            return DARK_THEMES.includes(lastDark) ? lastDark : DEFAULT_DARK_THEME;
        
        case 'manual':
        default:
            return storedTheme;
    }
}

/**
 * 按主题惰性注入字体样式，避免一次性加载全部主题字体。
 */
function ensureThemeFontStylesheet(theme) {
    const href = THEME_FONT_STYLESHEET[theme];
    if (!href) {
        return;
    }

    const linkId = `${THEME_FONT_LINK_PREFIX}${theme}`;
    if (document.getElementById(linkId)) {
        return;
    }

    const link = document.createElement('link');
    link.id = linkId;
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
}

/**
 * 应用主题到DOM
 */
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY_THEME, theme);
    ensureThemeFontStylesheet(theme);
    
    // 记忆该分组最后使用的主题
    const group = getThemeGroup(theme);
    if (group === 'light') {
        localStorage.setItem(STORAGE_KEY_LAST_LIGHT, theme);
    } else {
        localStorage.setItem(STORAGE_KEY_LAST_DARK, theme);
    }
}

/**
 * 更新UI显示
 */
function updateThemeUI(mode, theme) {
    // 更新模式按钮
    const modeBtn = document.getElementById('theme-mode-btn');
    if (modeBtn) {
        const iconEl = modeBtn.querySelector('[data-role="mode-icon"]');
        
        // 只使用SVG图标，无文字
        if (iconEl) {
            iconEl.innerHTML = SVG_ICONS[mode] || SVG_ICONS.auto;
        }
        modeBtn.dataset.currentMode = mode;
    }
    
    // 更新浮层中的选中态
    document.querySelectorAll('[data-action="select-theme"]').forEach(el => {
        const isActive = el.dataset.themeValue === theme;
        el.classList.toggle('active', isActive);
        el.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
}

/**
 * 设置模式（auto/light/dark）
 */
export function setThemeMode(mode) {
    localStorage.setItem(STORAGE_KEY_THEME_MODE, mode);
    const theme = resolveThemeByMode(mode);
    applyTheme(theme);
    updateThemeUI(mode, theme);
}

/**
 * 切换到下一个模式（循环）
 */
export function cycleThemeMode() {
    const currentMode = getThemeMode();
    const currentIndex = MODE_CYCLE.indexOf(currentMode);
    const nextIndex = (currentIndex + 1) % MODE_CYCLE.length;
    const nextMode = MODE_CYCLE[nextIndex];
    setThemeMode(nextMode);
}

/**
 * 手动选择具体主题（根据分组显示对应图标）
 */
export function setManualTheme(theme) {
    // 根据主题分组确定模式：亮色主题用'light'，暗色主题用'dark'
    const group = getThemeGroup(theme);
    const mode = group; // 'light' 或 'dark'

    localStorage.setItem(STORAGE_KEY_THEME_MODE, mode);
    applyTheme(theme);
    updateThemeUI(mode, theme);
}

/**
 * 初始化主题（页面加载时调用）
 */
export function initTheme() {
    const mode = getThemeMode();
    const theme = resolveThemeByMode(mode);
    applyTheme(theme);
    updateThemeUI(mode, theme);
    
    // 监听系统主题变化
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', () => {
        if (getThemeMode() === 'auto') {
            const newTheme = resolveThemeByMode('auto');
            applyTheme(newTheme);
            updateThemeUI('auto', newTheme);
        }
    });
}

/**
 * 获取所有主题列表（用于浮层渲染）
 */
export function getThemeList() {
    return {
        light: LIGHT_THEMES,
        dark: DARK_THEMES
    };
}
