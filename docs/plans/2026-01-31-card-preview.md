# 开包记录卡牌预览功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: 使用 superpowers:executing-plans 来逐任务实施此计划。

**目标:** 在开包记录页面实现点击卡牌放大预览功能，支持拖拽多角度查看（3D翻转效果）。

**架构:** 使用 CSS 3D transforms 实现卡牌翻转视觉效果，通过 JavaScript 监听鼠标/触摸事件计算旋转角度，模态框遮罩层使用固定定位覆盖全屏。

**技术栈:** HTML5, CSS3 (3D Transforms), Vanilla JavaScript, Jinja2 模板

**原始需求:** 需要在开包记录页面，点击卡牌时，能在屏幕中心放大并展示，还能拖拉多角度

---

## 准备工作

### Task 0: 创建任务清单

**文件:**
- 创建: `docs/plans/2026-01-31-card-preview.md` (本文档)

**说明:**
计划包含 5 个主要任务，涉及模板修改、JavaScript 功能实现、CSS 样式添加和本地化更新。

---

## Task 1: 修改 record_list.html 添加点击事件

**文件:**
- 修改: `src/ptcgp_auto_v2/web/templates/partials/record_list.html:54-90`

**步骤 1: 为卡牌容器添加点击属性和数据**

在 `record_list.html` 中修改卡牌项的 HTML，添加点击事件和必要的数据属性：

```html
<!-- 修改前 -->
<div class="card-item relative group aspect-[2/3] overflow-hidden transition-all duration-200 brutal-card">

<!-- 修改后 -->
<div class="card-item relative group aspect-[2/3] overflow-hidden transition-all duration-200 brutal-card cursor-pointer"
     onclick="openCardPreview(this)"
     data-card-name="{{ card.card_name }}"
     data-card-rarity="{{ card.rarity }}"
     data-card-set="{{ card.card.set_code if card.card else '' }}"
     data-card-number="{{ card.card.number if card.card else '' }}"
     data-card-image="{% if card.card and card.card.image_url %}https://wsrv.nl/?url=raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/cards-by-set/{{ card.card.set_code }}/{{ card.card.number }}.webp&w=800&output=webp{% else %}/static/card_back.png{% endif %}">
```

**步骤 2: 验证修改**

检查修改后的文件，确保：
1. 每个 `.card-item` 都有 `onclick="openCardPreview(this)"`
2. 数据属性正确包含卡牌信息
3. 图片 URL 使用更高分辨率 (w=800)

---

## Task 2: 在 main.js 添加卡牌预览功能

**文件:**
- 修改: `src/ptcgp_auto_v2/web/static/js/main.js`

**步骤 1: 添加卡牌预览全局状态变量**

在文件开头（常量声明之后）添加：

```javascript
// --- Card Preview State ---
let cardPreviewState = {
    isOpen: false,
    isDragging: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    rotateX: 0,
    rotateY: 0,
    targetElement: null
};
```

**步骤 2: 实现 openCardPreview 函数**

在 `showToast` 函数之后添加：

```javascript
// --- Card Preview Functions ---

function openCardPreview(cardElement) {
    // 防止重复打开
    if (cardPreviewState.isOpen) return;
    
    // 获取卡牌数据
    const cardName = cardElement.dataset.cardName || 'Unknown';
    const cardRarity = cardElement.dataset.cardRarity || '';
    const cardSet = cardElement.dataset.cardSet || '';
    const cardNumber = cardElement.dataset.cardNumber || '';
    const cardImage = cardElement.dataset.cardImage || '/static/card_back.png';
    
    // 创建预览模态框 HTML
    const previewHTML = `
        <div id="card-preview-overlay" class="card-preview-overlay" onclick="closeCardPreview(event)">
            <div id="card-preview-container" class="card-preview-container">
                <div id="card-preview-card" class="card-preview-card">
                    <div class="card-preview-front">
                        <img src="${cardImage}" alt="${cardName}" class="card-preview-image" onerror="this.src='/static/card_back.png'">
                    </div>
                    <div class="card-preview-back">
                        <img src="/static/card_back.png" alt="Card Back" class="card-preview-image">
                    </div>
                </div>
                <div class="card-preview-info">
                    <div class="card-preview-name">${cardName}</div>
                    <div class="card-preview-meta">
                        ${cardRarity ? `<span class="card-preview-rarity">${cardRarity}</span>` : ''}
                        ${cardSet ? `<span class="card-preview-set">${cardSet}</span>` : ''}
                        ${cardNumber ? `<span class="card-preview-number">#${cardNumber}</span>` : ''}
                    </div>
                </div>
                <div class="card-preview-hint">拖动旋转查看 / Drag to rotate</div>
            </div>
        </div>
    `;
    
    // 插入到 body
    document.body.insertAdjacentHTML('beforeend', previewHTML);
    
    // 更新状态
    cardPreviewState.isOpen = true;
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    cardPreviewState.targetElement = document.getElementById('card-preview-card');
    
    // 绑定拖拽事件
    bindCardPreviewEvents();
    
    // 禁止背景滚动
    document.body.style.overflow = 'hidden';
    
    // 添加显示动画
    requestAnimationFrame(() => {
        const overlay = document.getElementById('card-preview-overlay');
        if (overlay) overlay.classList.add('active');
    });
}
```

**步骤 3: 实现 closeCardPreview 函数**

```javascript
function closeCardPreview(event) {
    // 如果点击的是容器内部（卡牌本身），不关闭
    if (event && !event.target.id === 'card-preview-overlay') return;
    
    const overlay = document.getElementById('card-preview-overlay');
    if (!overlay) return;
    
    // 移除显示动画
    overlay.classList.remove('active');
    
    // 延迟后移除 DOM
    setTimeout(() => {
        overlay.remove();
        cardPreviewState.isOpen = false;
        cardPreviewState.targetElement = null;
        document.body.style.overflow = '';
    }, 300);
}
```

**步骤 4: 实现拖拽旋转逻辑**

```javascript
function bindCardPreviewEvents() {
    const container = document.getElementById('card-preview-container');
    if (!container) return;
    
    // 鼠标事件
    container.addEventListener('mousedown', handleDragStart);
    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);
    
    // 触摸事件
    container.addEventListener('touchstart', handleDragStart, { passive: false });
    document.addEventListener('touchmove', handleDragMove, { passive: false });
    document.addEventListener('touchend', handleDragEnd);
}

function handleDragStart(e) {
    if (!cardPreviewState.isOpen) return;
    
    cardPreviewState.isDragging = true;
    
    // 获取起始位置
    if (e.type === 'touchstart') {
        cardPreviewState.startX = e.touches[0].clientX;
        cardPreviewState.startY = e.touches[0].clientY;
    } else {
        cardPreviewState.startX = e.clientX;
        cardPreviewState.startY = e.clientY;
    }
    
    // 添加拖拽中样式
    const card = document.getElementById('card-preview-card');
    if (card) card.classList.add('dragging');
}

function handleDragMove(e) {
    if (!cardPreviewState.isDragging || !cardPreviewState.isOpen) return;
    
    e.preventDefault();
    
    // 获取当前位置
    let clientX, clientY;
    if (e.type === 'touchmove') {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }
    
    // 计算移动差值
    const deltaX = clientX - cardPreviewState.startX;
    const deltaY = clientY - cardPreviewState.startY;
    
    // 更新旋转角度（灵敏度：每像素 0.5 度）
    cardPreviewState.rotateY += deltaX * 0.5;
    cardPreviewState.rotateX -= deltaY * 0.5;
    
    // 限制 X 轴旋转范围 (-60 到 60 度)
    cardPreviewState.rotateX = Math.max(-60, Math.min(60, cardPreviewState.rotateX));
    
    // 应用旋转
    updateCardRotation();
    
    // 更新起始位置
    cardPreviewState.startX = clientX;
    cardPreviewState.startY = clientY;
}

function handleDragEnd() {
    if (!cardPreviewState.isDragging) return;
    
    cardPreviewState.isDragging = false;
    
    // 移除拖拽中样式
    const card = document.getElementById('card-preview-card');
    if (card) card.classList.remove('dragging');
}

function updateCardRotation() {
    const card = cardPreviewState.targetElement;
    if (!card) return;
    
    // 应用 3D 旋转
    card.style.transform = `rotateX(${cardPreviewState.rotateX}deg) rotateY(${cardPreviewState.rotateY}deg)`;
}
```

**步骤 5: 添加 ESC 键关闭支持**

在 `DOMContentLoaded` 事件监听器中添加：

```javascript
// Card preview ESC key support
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && cardPreviewState.isOpen) {
        closeCardPreview();
    }
});
```

---

## Task 3: 在 main.css 添加卡牌预览样式

**文件:**
- 修改: `src/ptcgp_auto_v2/web/static/css/main.css`

**步骤 1: 添加卡牌预览模态框基础样式**

在文件末尾添加：

```css
/* --- Card Preview Styles --- */

/* 遮罩层 */
.card-preview-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: var(--bg-overlay);
    backdrop-filter: blur(8px);
    z-index: 1000;
    display: flex;
    justify-content: center;
    align-items: center;
    opacity: 0;
    transition: opacity 0.3s ease;
    cursor: pointer;
}

.card-preview-overlay.active {
    opacity: 1;
}

/* 容器 */
.card-preview-container {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    cursor: grab;
    user-select: none;
    -webkit-user-select: none;
    touch-action: none;
}

.card-preview-container:active {
    cursor: grabbing;
}

/* 3D 卡牌容器 */
.card-preview-card {
    width: 400px;
    height: 560px;
    position: relative;
    transform-style: preserve-3d;
    transition: transform 0.1s ease-out;
    will-change: transform;
}

@media (max-width: 768px) {
    .card-preview-card {
        width: 280px;
        height: 392px;
    }
}

/* 卡牌正反面 */
.card-preview-front,
.card-preview-back {
    position: absolute;
    width: 100%;
    height: 100%;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.card-preview-front {
    transform: rotateY(0deg);
}

.card-preview-back {
    transform: rotateY(180deg);
}

/* 卡牌图片 */
.card-preview-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    border-radius: 16px;
}

/* 拖拽中样式 */
.card-preview-card.dragging {
    transition: none;
}

/* 卡牌信息 */
.card-preview-info {
    text-align: center;
    color: var(--text-color);
    background-color: var(--bg-surface);
    padding: 1rem 2rem;
    border-radius: var(--radius);
    border: var(--border-width) solid var(--border-color);
    box-shadow: var(--shadow-offset) var(--shadow-offset) 0px var(--shadow-color);
    max-width: 400px;
}

.card-preview-name {
    font-size: 1.25rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
    word-break: break-word;
}

.card-preview-meta {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    flex-wrap: wrap;
    font-size: 0.875rem;
    opacity: 0.8;
}

.card-preview-rarity,
.card-preview-set,
.card-preview-number {
    background-color: var(--bg-subtle);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-family: monospace;
}

/* 提示文字 */
.card-preview-hint {
    font-size: 0.75rem;
    opacity: 0.6;
    color: var(--text-color);
    text-align: center;
    margin-top: 0.5rem;
}

/* 主题适配 */
[data-theme="retro"] .card-preview-info {
    background-color: #000;
    border-color: var(--text-color);
}

[data-theme="luxury"] .card-preview-info {
    background-color: #1a1a1a;
    border-color: var(--border-color);
}

[data-theme="luxury"] .card-preview-front,
[data-theme="luxury"] .card-preview-back {
    box-shadow: 0 20px 60px rgba(212, 175, 55, 0.3);
}
```

**步骤 2: 验证样式兼容性**

检查：
1. 所有 CSS 变量都已定义
2. 移动端响应式样式正确
3. 各主题适配样式完整

---

## Task 4: 更新本地化文件

**文件:**
- 修改: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- 修改: `src/ptcgp_auto_v2/web/locales/en.json`

**步骤 1: 添加中文本地化**

在 `zh_CN.json` 末尾添加：

```json
    "card_preview_hint": "拖动旋转查看",
    "card_preview_close_hint": "点击空白处或按 ESC 关闭"
```

**步骤 2: 添加英文本地化**

在 `en.json` 末尾添加（在最后一个键值对前加逗号）：

```json
    "card_preview_hint": "Drag to rotate",
    "card_preview_close_hint": "Click outside or press ESC to close"
```

**步骤 3: 更新 JS 中的提示文本**

修改 `main.js` 中的 `openCardPreview` 函数，将硬编码的提示文本改为从 data 属性获取或使用本地化键：

由于当前模板没有传递 t 对象到 JS，暂时使用硬编码的双语提示：

```javascript
<div class="card-preview-hint">拖动旋转查看 / Drag to rotate</div>
```

后续可以通过在 HTML 中添加 `data-lang` 属性来支持完整本地化。

---

## Task 5: 功能测试

**步骤 1: 启动 Web 服务**

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto
python main_v2.py --web
```

**步骤 2: 测试功能清单**

- [ ] 点击卡牌正常打开预览模态框
- [ ] 卡牌在屏幕中心显示，尺寸正确
- [ ] 3D 翻转效果正常工作
- [ ] 鼠标拖拽可旋转卡牌
- [ ] 触摸拖拽可旋转卡牌（移动端）
- [ ] 点击遮罩层关闭模态框
- [ ] 按 ESC 键关闭模态框
- [ ] 关闭后背景滚动恢复
- [ ] 各主题下样式正确显示
- [ ] 移动端响应式正常

**步骤 3: 提交代码**

```bash
git add src/ptcgp_auto_v2/web/templates/partials/record_list.html
git add src/ptcgp_auto_v2/web/static/js/main.js
git add src/ptcgp_auto_v2/web/static/css/main.css
git add src/ptcgp_auto_v2/web/locales/zh_CN.json
git add src/ptcgp_auto_v2/web/locales/en.json
git commit -m "feat: add card preview with 3D rotation on click

- 点击卡牌可在屏幕中心放大预览
- 支持鼠标/触摸拖拽旋转查看
- 适配多主题和移动端响应式
- 支持 ESC 键和点击遮罩层关闭"
```

---

## 注意事项

1. **性能优化**: 使用 `will-change: transform` 和 `transform-style: preserve-3d` 确保动画流畅
2. **移动端适配**: 触摸事件需要 `preventDefault` 防止页面滚动
3. **浏览器兼容**: 3D transforms 支持 Chrome 36+, Firefox 16+, Safari 9+, Edge 12+
4. **无障碍**: 支持 ESC 键关闭，后续可添加 ARIA 标签
5. **图片加载**: 使用高分辨率图片 (w=800) 确保放大后清晰度

---

## 可选增强（未来版本）

1. 添加卡牌详细信息的右侧/底部面板
2. 支持键盘方向键旋转
3. 添加"查看原图"链接跳转到原始图片
4. 支持卡牌收藏/标记功能
5. 添加分享按钮生成卡牌图片链接
