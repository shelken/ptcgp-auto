# Phase 2: 详情展示与 Markdown 渲染 - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

用户点击通知项，展开详情区域，查看 Markdown 渲染后的完整内容。点击后自动标记已读。Markdown 渲染前需进行 XSS 防护。

</domain>

<decisions>
## Implementation Decisions

### 展开交互方式
- 整行可点击（点击通知项任意位置都可展开/收起）
- 手风琴模式（同时只能展开一条通知）
- 展开后自动滚动到详情区域，确保内容可见
- 展开/收起有平滑的高度过渡动画

### 详情内容呈现
- 详情区域无高度限制，内容多长就多长
- 图片宽度自适应容器，不提供点击放大功能
- 链接点击时新标签页打开（target="_blank"）
- 不需要代码块样式支持

### Markdown 支持范围
- 最小语法集合：粗体、斜体、链接
- 不支持表格
- 不支持任务列表
- 纯文本 URL 自动转为可点击链接

### 已读标记时机
- 点击通知项时立即标记为已读
- 视觉反馈立即变化（粗体→普通字体），不等待后端响应
- 后端接口异步调用，不阻塞 UI
- 接口失败时静默忽略，保持 UI 变化

### Claude's Discretion
- 动画的具体时长和缓动函数
- 自动滚动的偏移量（避免被面板标题遮挡）
- XSS 防护的具体配置（允许的标签和属性）

</decisions>

<specifics>
## Specific Ideas

- "手风琴模式"避免用户同时展开多条通知导致列表过长难以浏览
- 异步调用 + 静默忽略的策略优先保证用户体验流畅

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-markdown*
*Context gathered: 2026-02-23*
