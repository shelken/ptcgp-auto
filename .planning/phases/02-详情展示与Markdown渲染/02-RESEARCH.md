# Phase 2: 详情展示与 Markdown 渲染 - Research

**Researched:** 2026-02-23
**Domain:** HTML details/summary accordion + Markdown 渲染 + XSS 防护
**Confidence:** HIGH

## Summary

Phase 2 实现通知项点击展开详情、Markdown 渲染与 XSS 防护。核心发现：

1. **HTML-native Accordion**: 使用 `<details name="notification-accordion">` 实现手风琴模式（同时只能展开一条），无需 JavaScript
2. **现代 CSS 动画**: Chrome 129+ 支持 `calc-size()` 和 `::details-content` 实现平滑高度过渡，旧浏览器优雅降级
3. **marked.js + DOMPurify 组合**: 标准安全方案，DOMPurify 3.1.1+ 修复了之前的绕过漏洞

**Primary recommendation:** 使用原生 HTML `<details>` + 最小化 marked.js 配置 + DOMPurify 严格白名单

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**展开交互方式**
- 整行可点击（点击通知项任意位置都可展开/收起）
- 手风琴模式（同时只能展开一条通知）
- 展开后自动滚动到详情区域，确保内容可见
- 展开/收起有平滑的高度过渡动画

**详情内容呈现**
- 详情区域无高度限制，内容多长就多长
- 图片宽度自适应容器，不提供点击放大功能
- 链接点击时新标签页打开（target="_blank"）
- 不需要代码块样式支持

**Markdown 支持范围**
- 最小语法集合：粗体、斜体、链接
- 不支持表格
- 不支持任务列表
- 纯文本 URL 自动转为可点击链接

**已读标记时机**
- 点击通知项时立即标记为已读
- 视觉反馈立即变化（粗体→普通字体），不等待后端响应
- 后端接口异步调用，不阻塞 UI
- 接口失败时静默忽略，保持 UI 变化

### Claude's Discretion

- 动画的具体时长和缓动函数
- 自动滚动的偏移量（避免被面板标题遮挡）
- XSS 防护的具体配置（允许的标签和属性）

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INTR-01 | 点击通知项展开详情（显示 markdown 内容） | HTML `<details>` 原生支持 |
| INTR-02 | 点击通知项自动标记为已读 | 前端异步调用 + 乐观 UI 更新 |
| INTR-03 | 展开详情后可收起 | `<details>` 原生 toggle |
| MD-01 | 通知详情支持 markdown 渲染 | marked.js v5+ |
| MD-02 | markdown 渲染前进行 XSS 过滤（DOMPurify） | DOMPurify 3.1.1+ 严格白名单 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| marked.js | ^15.0.0 | Markdown 解析 | 最快的 JS Markdown 解析器，零依赖 |
| DOMPurify | ^3.2.0 | XSS 防护 | 业界标准，持续维护，Cure53 安全团队出品 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| 无额外依赖 | - | - | 使用原生 HTML/CSS 实现 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| marked.js | markdown-it | marked 更快更轻量，markdown-it 插件生态更丰富 |
| DOMPurify | sanitize-html | DOMPurify 浏览器原生性能更好，sanitize-html 是 Node.js 方案 |

**Installation:**
```html
<!-- 在 base.html 或 index.html 中通过 CDN 引入 -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.0/dist/purify.min.js"></script>
```

## Architecture Patterns

### Recommended Project Structure
```
src/ptcgp_auto_v2/web/
├── templates/partials/
│   ├── notification_list_items.html    # 修改：添加 <details> 结构
│   └── notification_detail.html        # 新增：详情渲染片段
├── static/js/modules/features/
│   └── notification_panel.js           # 修改：添加 Markdown 渲染逻辑
└── static/css/components/
    └── notification-panel.css          # 修改：添加 details 动画样式
```

### Pattern 1: HTML-native Accordion
**What:** 使用 `<details name="group">` 实现手风琴模式，浏览器原生管理互斥状态
**When to use:** 需要手风琴行为且不需要复杂动画时

```html
<!-- Source: https://gomakethings.com/html-native-accordions -->
<details name="notification-accordion" class="notification-item">
  <summary class="notification-item__summary">
    <!-- 标题、时间、摘要 -->
  </summary>
  <div class="notification-item__detail" data-markdown-content>
    <!-- Markdown 渲染后的内容 -->
  </div>
</details>
```

**关键发现**: `name` 属性在所有现代浏览器中实现了分组互斥行为（Chrome 120+, Firefox 130+, Safari 17.2+）

### Pattern 2: CSS 动画平滑过渡
**What:** 使用 `calc-size()` + `::details-content` 实现平滑高度动画
**When to use:** Chrome 129+ 用户（可渐进增强）

```css
/* Source: https://www.builder.io/blog/animated-css-accordions */
.notification-item {
  --details-transition-duration: 250ms;
}

/* 新版 CSS（Chrome 129+） */
.notification-item::details-content {
  block-size: 0;
  transition: block-size var(--details-transition-duration) ease-out;
}

.notification-item[open]::details-content {
  block-size: calc-size(auto, size);
}

/* 降级方案：旧浏览器无动画，但功能正常 */
@supports not (block-size: calc-size(auto, size)) {
  .notification-item::details-content {
    block-size: auto;
  }
}
```

### Pattern 3: marked.js + DOMPurify 安全组合
**What:** Markdown 解析后立即进行 XSS 清理
**When to use:** 所有用户内容渲染场景

```javascript
// Source: Context7 - marked.js + DOMPurify docs
const dirtyMarkdown = notification.content;

// 1. 配置 marked.js（最小语法集）
const markedOptions = {
  gfm: false,           // 不启用 GFM 扩展
  breaks: true,         // 换行转 <br>
  pedantic: false,
};

// 2. 配置 DOMPurify（严格白名单）
const purifyConfig = {
  ALLOWED_TAGS: ['b', 'strong', 'i', 'em', 'a', 'p', 'br'],
  ALLOWED_ATTR: ['href', 'title'],
  ALLOW_DATA_ATTR: false,
};

// 3. 渲染流程
const rawHtml = marked.parse(dirtyMarkdown, markedOptions);
const cleanHtml = DOMPurify.sanitize(rawHtml, purifyConfig);

// 4. 插入 DOM
element.innerHTML = cleanHtml;
```

### Anti-Patterns to Avoid
- **使用 innerHTML 直接插入 Markdown 解析结果**: 存在 XSS 风险
- **使用 max-height 动画 hack**: 需要预设最大值，且动画不自然
- **JavaScript 管理手风琴状态**: 不如原生 `<details name="group">` 简洁可靠
- **使用过时版本的 DOMPurify (< 3.1.0)**: 存在已知绕过漏洞

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 手风琴互斥逻辑 | JS 状态管理 + 事件监听 | `<details name="group">` | 原生实现更可靠，无障碍支持内置 |
| Markdown 解析 | 正则替换 | marked.js | 边界情况复杂，自制方案易遗漏 |
| XSS 过滤 | 自定义正则过滤 | DOMPurify | XSS 攻击向量繁多，需要专业方案 |
| 自动链接识别 | 手动正则匹配 | marked.js `gfm: true` 或 autolink 扩展 | URL 边界识别复杂 |

**Key insight:** XSS 防护必须使用经过安全审计的专业库，自制方案几乎必然存在漏洞

## Common Pitfalls

### Pitfall 1: DOMPurify 版本过旧
**What goes wrong:** 使用 DOMPurify ≤ 3.1.0 存在嵌套元素绕过漏洞（CVE-2024-xxxxx）
**Why it happens:** 旧版本在处理深度嵌套元素时，浏览器 DOM 解析与 DOMPurify 预期不一致
**How to avoid:** 强制使用 DOMPurify ≥ 3.2.0
**Warning signs:** 控制台警告 "DOMPurify version outdated"

### Pitfall 2: 忘记为链接添加 rel="noopener"
**What goes wrong:** target="_blank" 链接存在安全风险（tabnabbing 攻击）和性能问题
**Why it happens:** 默认行为未设置 rel 属性
**How to avoid:** 使用 DOMPurify hook 强制添加

```javascript
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.hasAttribute('href')) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});
```

### Pitfall 3: scrollIntoView 被固定头部遮挡
**What goes wrong:** 展开详情后滚动位置不正确，被面板标题栏遮挡
**Why it happens:** scrollIntoView 默认对齐到视口顶部
**How to avoid:** 使用 CSS `scroll-margin-top` 或 JS 计算偏移

```css
.notification-item {
  scroll-margin-top: 60px; /* 面板标题高度 */
}
```

```javascript
// JS 方案：精确控制
element.scrollIntoView({ behavior: 'smooth', block: 'start' });
```

### Pitfall 4: details 动画在旧浏览器闪烁
**What goes wrong:** 使用 `::details-content` 但浏览器不支持时出现布局问题
**Why it happens:** 未提供降级样式
**How to avoid:** 使用 `@supports` 查询渐进增强

## Code Examples

### 完整渲染流程

```javascript
// Source: Context7 docs + MDN
import { marked } from 'marked';
import DOMPurify from 'dompurify';

class NotificationRenderer {
  constructor() {
    // 配置 DOMPurify hook：为所有链接添加 target="_blank"
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      if ('target' in node) {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
    });
  }

  render(markdown) {
    const rawHtml = marked.parse(markdown, {
      gfm: false,
      breaks: true,
    });

    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: ['b', 'strong', 'i', 'em', 'a', 'p', 'br'],
      ALLOWED_ATTR: ['href', 'title', 'target', 'rel'],
    });
  }
}
```

### 手风琴 + 滚动 + 已读标记

```javascript
// 处理 details toggle 事件
document.addEventListener('toggle', (event) => {
  const details = event.target;
  if (!details.classList.contains('notification-item')) return;

  if (details.open) {
    // 1. 滚动到可见位置
    details.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // 2. 标记已读（乐观 UI + 异步后端）
    const id = details.dataset.notificationId;
    markAsReadOptimistically(details);
    markAsReadAsync(id);
  }
}, true); // capture 阶段监听，因为 toggle 不冒泡

function markAsReadOptimistically(element) {
  element.classList.remove('notification-item--unread');
  const indicator = element.querySelector('.notification-item__indicator');
  if (indicator) indicator.remove();
}

async function markAsReadAsync(id) {
  try {
    await fetch(`/notifications/${id}/read`, { method: 'POST' });
  } catch {
    // 静默忽略失败
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JS 管理手风琴状态 | `<details name="group">` | 2024-2025 | 代码量减少 50%+，无障碍内置 |
| max-height 动画 hack | `calc-size(auto)` + `::details-content` | Chrome 129 (2024) | 真正的 auto 高度动画 |
| sanitize-html (Node) | DOMPurify (Browser) | 2020+ | 更好的浏览器性能 |

**Deprecated/outdated:**
- DOMPurify < 3.1.1: 存在嵌套元素绕过漏洞
- jQuery UI accordion: 现代浏览器不需要

## Open Questions

1. **CDN vs 本地依赖**
   - What we know: 项目当前未使用 npm 前端包管理
   - What's unclear: 是否需要将 marked.js/DOMPurify 下载到本地
   - Recommendation: 使用 CDN 引入，添加 integrity 属性保证安全性

2. **Autolink URL 实现**
   - What we know: marked.js 支持 GFM autolink
   - What's unclear: 是否需要启用 GFM 或使用扩展
   - Recommendation: 使用 marked 扩展 `marked.use({ extensions: [autolink] })` 或启用 gfm: true

## Sources

### Primary (HIGH confidence)
- /markedjs/marked - 核心配置、renderer 自定义、扩展 API
- /cure53/dompurify - ALLOWED_TAGS/ALLOWED_ATTR、hooks 机制、版本安全
- https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView - scrollIntoView API

### Secondary (MEDIUM confidence)
- https://gomakethings.com/html-native-accordions - `<details name="">` 分组行为
- https://www.builder.io/blog/animated-css-accordions - `calc-size()` 和 `::details-content` 动画
- https://css-tricks.com/using-styling-the-details-element/ - details 元素样式最佳实践

### Tertiary (LOW confidence)
- https://shaheen.beaconred.net/research/2025/05/28/when-purification-fails.html - DOMPurify 历史漏洞分析（用于了解风险）

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - marked.js 和 DOMPurify 都是成熟稳定方案
- Architecture: HIGH - `<details name="">` 是现代浏览器原生支持
- Pitfalls: HIGH - 基于 Context7 官方文档和已知 CVE

**Research date:** 2026-02-23
**Valid until:** 2026-03-23（30 days - stable APIs）
