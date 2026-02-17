# Web 模块代码结构

## 最高原则

- 每次遇到新问题并解决了，必须把正确方式写回下面的常见问题与注意点，简洁点，必须先抽象出问题所在，不是直接说明具体细节，而是只要用关键词提及就行。
- 每次写ui界面时，先把当前的main.css文件读一遍

## 目录结构

```
src/ptcgp_auto_v2/web/
├── app.py                      # FastAPI 主应用入口（初始化与路由挂载）
├── routers/                    # 路由层（参数解析/响应拼装）
│   ├── index.py
│   ├── records.py
│   ├── owned_cards.py
│   ├── tasks.py
│   ├── management.py
│   ├── plans.py
│   ├── metadata.py
│   ├── pack_config.py
│   └── exchange_card.py
├── services/                   # 业务层（视图模型/业务组合）
│   ├── index_service.py
│   ├── record_service.py
│   ├── owned_card_service.py
│   ├── task_service.py
│   ├── plan_service.py
│   ├── metadata_service.py
│   ├── pack_config_service.py
│   ├── exchange_card_service.py
│   └── account_service.py
├── queries/                    # 查询层（SQL 构造/分页过滤）
│   ├── record_queries.py
│   ├── owned_card_queries.py
│   ├── task_queries.py
│   ├── metadata_queries.py
│   └── exchange_card_queries.py
├── utils/                      # 工具模块
│   ├── form_utils.py          # 表单处理工具函数
│   ├── element_utils.py       # 元素归一化工具
│   ├── i18n.py                # 多语言加载与校验
│   ├── template_env.py        # 模板初始化
│   └── view_helpers.py        # 视图辅助方法
├── templates/                  # Jinja2 模板
│   ├── index.html             # 主页面（单页应用，包含所有 Tab）
│   └── partials/              # 局部模板（用于 HTMX 动态加载）
│       ├── account_list.html   # 账号列表
│       ├── plan_list.html      # 计划列表
│       ├── record_list.html    # 开包记录列表
│       ├── metadata_list.html  # 卡包元数据列表
│       ├── exchange_card_list.html # 交换记录列表
│       ├── options_boosters.html # 补充包选项
│       ├── macros/             # 宏定义（可复用组件）
│       │   ├── modal.html      # 模态框宏
│       │   ├── forms.html      # 表单宏
│       │   └── tables.html     # 表格宏
│       └── modals/             # 模态框模板
│           ├── edit_account.html
│           ├── edit_account_plans.html
│           ├── edit_pack_config.html
│           └── edit_plan.html
├── static/                     # 静态资源
│   ├── css/
│   │   └── main.css           # 主样式文件（CSS 变量 + 工具类）
│   └── js/
│       ├── main.js             # 主 JS 入口
│       └── modules/            # ES6 模块
│           ├── bootstrap.js      # 启动编排（初始化顺序与首屏恢复）
│           ├── event_bindings.js # 全局事件绑定（click/change/input/submit/htmx）
│           ├── action_handlers.js # data-action 动作分发与业务入口
│           ├── tabs.js           # Tab 切换
│           ├── ui_preferences.js # 语言/视图/筛选面板偏好状态
│           ├── relative_time.js  # 相对时间渲染
│           ├── auto_refresh.js   # 自动刷新 URL 构造
│           ├── constants.js      # 管理页 hash 等共享常量
│           ├── custom_select.js  # 自定义下拉
│           ├── modal.js          # 模态框处理
│           ├── theme.js          # 主题与模式切换
│           ├── utils.js          # 工具函数（toast、throttle、debounce 等）
│           └── features/         # 页面/业务域模块
│               ├── daily_gift.js
│               ├── exchange_cards.js
│               ├── owned_cards.js
│               ├── plans.js
│               ├── tasks.js
│               ├── card_preview.js
│               └── filters/
│                   ├── index.js
│                   ├── shared_form.js
│                   ├── records_filters.js
│                   ├── owned_filters.js
│                   └── tasks_filters.js
├── locales/                    # 国际化文件
│   ├── en.json                # 英文翻译
│   └── zh_CN.json             # 中文翻译
└── AGENTS.md                  # 本文件
```

## 核心架构

### 后端 (FastAPI)

- **app.py**: 主应用入口，仅负责初始化与路由挂载
  - 路由采用 RESTful 风格，返回 HTML 片段供 HTMX 使用
  - 依赖注入 `get_fastapi_session` 获取数据库会话
  - i18n 与模板初始化在 `utils/` 中集中管理
  - Jinja2 过滤器：`datetime` 用于格式化日期
- **routers/**: 路由层，仅处理参数解析与响应拼装
- **services/**: 业务层，负责视图模型与业务拼装
- **queries/**: 查询层，负责 SQL 构造与分页过滤

### 前端 (HTMX + ES6 Modules)

- **index.html**: 单页应用入口，包含所有 Tab 容器
  - 使用 HTMX 进行局部页面更新
  - Tab 切换通过 `hx-get` 加载 `partials/` 下的模板
- **JS 架构**: ES6 模块化
  - `main.js`: 主入口，仅调用 `bootstrap.initApp()`
  - `modules/bootstrap.js`: 仅负责初始化编排，不承载动作分发细节
  - `modules/event_bindings.js`: 集中管理全局事件绑定与 HTMX 生命周期监听
  - `modules/action_handlers.js`: 处理模板 `data-action` 分发，保持模板无内联事件
  - `modules/features/*`: 页面/业务域逻辑（daily-gift、exchange-cards、owned-cards、plans、tasks 等）
  - `modules/features/filters/*`: 按 records/owned/tasks 分拆筛选逻辑，`shared_form.js` 负责通用序列化/回填
  - `modules/utils.js`: 工具函数（toast、throttle、debounce、元素可见性检测）
- **CSS 架构**: CSS 变量驱动主题
  - `main.css` 定义主题变量和工具类
  - 支持多主题（Retro、Luxury、Organic 等）

## 开发规范

### 本地化 (i18n)

- 页面任何文本显示必须做本地化处理
- 在 `locales/` 目录下添加翻译键值对
- 变更界面时需要同步更新 `locales/*.json` 的内容

### 静态文件缓存

- 修改 `static/css/main.css` 或 `static/js/main.js` 后
- 必须同步更新 `templates/index.html` 中的版本号参数（如 `?v=2.3` → `?v=2.4`）
- 强制浏览器加载最新文件而非缓存版本

### 多主题适配（严格禁止硬编码颜色）

- **严禁** 使用硬编码的颜色类（如 `bg-white`, `bg-black`, `text-gray-500`, `border-black` 等）
- **必须** 使用基于 CSS 变量的 Utility 类：

| 类型 | 工具类 | 说明 |
|------|--------|------|
| 背景 | `.bg-theme` | 页面背景 |
| | `.bg-card` | 卡片/输入框 |
| | `.bg-surface` | 纯净表面 |
| | `.bg-overlay` | 遮罩 |
| | `.bg-subtle` | 细微背景 |
| | `.bg-separator` | 分割线 |
| 边框 | `.border-theme` | 主边框 |
| | `.border-subtle` | 细微边框 |
| | `.border-subtle-light` | 更浅边框 |
| 文本 | `.text-theme` | 主文本 |
| | `.text-muted` | 次要/说明文本 |
| 交互 | `.hover-bg-subtle` | 悬停背景 |
| | `.hover-border-theme` | 悬停边框 |
| | `.brutal-btn` | 按钮样式 |
| | `.brutal-input` | 输入框样式 |

- 新增 UI 组件时，请参考 `main.css` 中的变量定义
- 确保在所有主题（Retro, Luxury, Organic 等）下表现正常

### 新增功能流程

1. **后端 API**: 在 `routers/` 添加新路由，并在 `services/`/`queries/` 补齐逻辑
2. **模板**: 在 `templates/partials/` 添加局部模板（如需要）
3. **宏组件**: 通用组件请添加到 `templates/partials/macros/`
4. **本地化**: 在 `locales/*.json` 添加翻译键
5. **前端逻辑**: 如需新 JS 功能，在 `static/js/` 添加模块
6. **缓存版本**: 更新 `templates/index.html` 中的 CSS/JS 版本号

### 自动刷新组件（必须）

- 所有可独立刷新的页面容器必须使用 `auto_refresh_container` 宏封装
- 统一通过 `data-auto-refresh` 与可选的 `data-refresh-include` 提供刷新 URL 与筛选参数
- 需要替换整个容器时使用 `data-refresh-swap="outerHTML"`

## 常见问题与注意点（经验总结）

- **表单状态一致性**：界面上的启用/排序/选项变更要同步写回表单字段，确保提交数据与操作一致。
- **布局约束**：关键输入区需设定对齐/宽度/间距约束，避免不同内容长度或断点下错位与遮挡。
- **Modal 交互一致性**：必须复用 `modal.html` 宏与 `modules/modal.js` 逻辑；遮罩点击关闭、关闭按钮可见性与滚动锁定要一致。
- **滚动锁定**：打开 Modal 时同时锁定 `body` 与 `html` 的滚动，避免滚轮影响主页面。
- **自定义 Select**：`hx-on` 里调用的函数需挂到 `window`；恢复选择时需要 `reinitCustomSelect` 刷新 UI。
- **自定义 Select 事件**：触发 `change` 必须冒泡（`new Event('change', { bubbles: true })`），否则 HTMX 表单不刷新；搜索框回车需 `preventDefault()` 防止整页刷新。
- **自定义 Select 键盘**：需要支持上下键/回车/ESC 的统一行为，避免各处单独实现导致体验不一致。
- **筛选恢复与作用域**：恢复筛选时必须在对应表单内查找元素，避免命中其他 Tab 的同名输入。
- **筛选参数合法性**：筛选参数可能为空字符串（如 `account_id=`），后端需容错解析，避免 422。
- **HTMX 请求去重**：不要在恢复状态时触发多次 `change`；避免写回带参数的 `data-url`，使用 `data-base-url` 构建请求。
- **自动刷新限流**：自动刷新必须有并发锁/节流，避免同一事件链（focus/可见性/重渲染）触发重复请求或无关请求。
- **HTMX 局部替换**：表格分页/滚动加载时避免重复渲染表头；只替换 `tbody` 行或使用哨兵行。
- **排序参数传递**：排序控件若不在表单内部，需要在 `hx-include` 明确包含该控件，否则请求丢参。
- **表头排序绑定**：交互控件在表单外时，事件绑定必须覆盖文档范围，避免只在局部容器内查找导致点击无效。
- **Tab 恢复**：根据 hash 恢复时仍需触发切换动作，避免停留在默认 Tab。
- **默认视图兜底**：首次进入页面（无 hash/无缓存）需设置明确默认 Tab 并触发加载，否则出现空白且无请求。
- **元素值归一化**：属性/元素字段注意大小写归一，避免出现重复选项与筛选失效。
- **时间展示一致性**：列表中的时间字段建议统一为“相对时间 + 悬浮具体时间”；HTMX swap 后需要重新调用 `updateRelativeTimes`，且根节点本身也可能是 `data-relative-locale` 容器。
- **管理页时间渲染规范**：管理类 partial（如 friendship）中的时间列必须使用 `.relative-time + data-iso + data-tooltip` 结构，禁止仅输出 `|datetime` 绝对时间。
- **Tooltip**：优先使用 `data-tooltip` + 自定义样式，避免依赖浏览器原生 title 在主题/样式下不可见。
- **筛选条件缓存**：所有列表页面的筛选条件必须缓存（如 localStorage），避免刷新/切换后需要重新选择；恢复时注意不要触发重复请求。
- **筛选统一策略**：所有带筛选的列表页面必须使用统一的序列化/恢复逻辑（`serializeFormFilters`/`applyFormFilters`/`buildQueryParts`），避免各页面各写一套。
- **自定义 Select 初始化兜底**：HTMX/动态插入 DOM 后需确保自定义 Select 被自动初始化（可使用 MutationObserver 兜底），防止退回浏览器默认样式。
- **相对时间更新**：筛选/分页追加后要重新更新相对时间；`updateRelativeTimes` 需要能处理根节点与其最近容器。
- **相对时间展示一致**：所有列表中的时间字段统一使用“相对时间 + 悬浮具体时间”，并在 HTMX 替换后重算，避免筛选后回退成绝对时间。
- **相对时间容器前置条件**：任何通过 HTMX 局部刷新的容器（如 `#management-content`）若包含 `.relative-time`，必须在该容器或其祖先提供 `data-relative-locale` 与相对时间文案数据；否则 `updateRelativeTimes` 不会生效。
- **关联预加载原则**：跨线程/跨会话使用 ORM 对象时，必须显式预加载所需关联，避免脱离 session 后数据缺失。
- **筛选恢复请求冲突**：恢复筛选仅回填 UI，不主动触发请求；首次加载由入口请求负责，避免“默认请求 + 恢复请求”双发。
- **隐藏区域请求隔离**：HTMX 触发前需检查当前 Tab/容器是否激活，避免隐藏区域误触发请求。
- **事件委托迁移规范**：将 `onclick/onchange` 迁移到 `data-action` 后，必须在 `bootstrap.js` 同步补全对应分发分支，并删除 `main.js` 中已不再需要的 `window.xxx` 导出，避免“模板已改、全局函数残留/缺失”造成回归。
- **事件绑定时序**：依赖 `restoreTab()` 的页面初始化必须先绑定 `document.body` 事件委托，再执行 `restoreTab()`；否则 `restoreTab()` 内部触发的 `click()` 不会被分发，导致首屏不加载。
- **动作类型与事件类型匹配**：`select` 触发类动作（如 `add-plan`、`set-theme`）必须走 `change` 委托，不要放在 `click` 委托中，避免误触或漏触发。
- **Modal 关闭规范**：遮罩点击关闭应统一走 `modules/modal.js` 的容器监听，不再在模板中写 `onclick="if(event.target===this) closeModal()"`，防止重复逻辑。
- **模板事件规范（强制）**：`templates/` 与 `templates/partials/` 禁止新增 `onclick/onchange/oninput/onsubmit` 内联逻辑；统一使用 `data-action` + `bootstrap.js` 事件委托。
- **管理页弹窗打开规范**：触发 `hx-get` 且 `hx-target="#modal-content"` 的按钮不再手动操作 `#modal-container` 显隐，统一依赖 `htmx:afterSwap` + `getModal().openFromSwap()`。
- **状态同步规范**：跨表单状态同步（如 friendship/daily-gift 隐藏字段）必须走委托处理（`change/submit`），不要把 `document.querySelector(...).value=...` 写在模板属性里。
- **元数据折叠规范**：分区折叠逻辑放在模块函数（如 `toggleSection`）中，通过 `data-target-id/data-icon-id` 驱动；禁止在 partial 内嵌 `<script>`。
- **图片兜底规范**：禁止引用不存在的 `/static/*.png` 占位图；如果不需要占位背景，统一使用透明 data URI 作为最终兜底，避免额外静态资源依赖。
- **onerror 防循环规范**：在图片 `onerror` 回退分支必须先 `this.onerror = null`，再改 `src`，避免 fallback 资源异常时产生无限 404 请求刷屏。
- **旧缓存兼容规范**：当静态资源路径发生变更时，优先通过版本号更新与前端统一回退策略清除旧引用，避免继续依赖临时兼容路由。
- **任务2.2 DOM 安全规范**：在 `features/plans.js`、`features/filters/*.js` 这类用户可触发的动态区域，禁止再使用字符串 `innerHTML` 拼接按钮/卡片；统一使用 `createElement + textContent + replaceChildren`。
- **筛选组清空规范**：拥有卡牌页若提供“分组清空”，必须在前端一次性批量取消选中并只触发一次列表刷新，避免逐个 checkbox 触发多次 HTMX 请求。
- **分段控件状态同步**：类似列数切换的 segmented 按钮，除视觉 `active` 外还要同步 `aria-pressed`，防止状态和实际值不一致。
- **左栏滚动一致性**：当页面被定义为“左筛选 + 右内容”整体滚动时，不要给左栏卡片加 `sticky`；否则鼠标在左栏滚轮会触发页面滚动但左栏固定不动，造成两栏不同步的错觉。
- **Modal 成功关闭规范**：提交成功后关闭弹窗统一使用 `data-close-modal-on-success="true" + bootstrap.js(hx-afterRequest)`，不要在模板里写 `hx-on:...closeModal()`。
- **任务手动重置优先级**：`reset-completed` 把任务改回 `pending` 时必须同时清空 `next_run_at`（设为 `NULL`），否则未来时间会导致重置任务被已到期任务长期抢占。
- **管理页 hash 白名单同步**：新增管理子页（如 `exchange-cards`）时，必须同时更新 `tabs.js` 与 `bootstrap.js` 中的 hash 白名单，否则刷新/直达时不会自动加载对应页面。
- **业务日期一致性**：`daily-gift` 的默认日期与“Today”按钮必须使用后端下发的游戏业务日期（如 UTC06:00+offset 计算），不能直接用前端自然日 `new Date()`。
- **标识信息分层展示原则**：任何列表中的账号/好友标识均采用“可读名称主行 + 标识 ID 次行（弱化）”展示，避免由 ID 主导造成阅读负担。
- **复合字段合并展示原则**：当多个关联标识需要合并到同一列时，主业务标识独立首行，补充标识放次行弱化展示，确保信息密度与可读性平衡。
- **状态附加信息展示原则**：所有状态列统一规则为：只要失败理由字段（如 `failed_reason` / `error_message`）有值，就把失败理由挂载到状态 tooltip；不依赖状态枚举判断。不再额外保留独立“错误/失败原因”列。
- **多时间语义展示原则**：同一记录存在“创建/更新”双时间语义时，列表主展示优先使用更新时间，创建时间作为 tooltip 辅助信息保留。
- **枚举值本地化原则**：请求类型、状态等枚举字段禁止直接渲染原始值；统一通过 i18n key 映射展示，并保留原值兜底。
- **状态组件复用原则**：所有列表状态列统一复用状态组件（`status_chip`），由组件内部处理本地化、主题色映射与失败理由 tooltip，禁止各页面手写分支。
- **术语统一原则（朋友id）**：Web 中文文案中涉及 `friend_id` 的用户可见文本统一使用“朋友id”，避免混用“Friend ID/friend_id/好友ID”等写法。
- **跨列表一致性原则**：管理页新增展示规范后，需同步检查同类列表（如 friendship/exchange/daily-gift/tasks）并统一落地，避免同一概念在不同列表出现风格漂移。
- **CSS 组件单一来源原则**：状态/标签等跨页面复用的组件样式必须集中到单一 CSS 文件（如 `status-chip.css`），禁止在多处重复定义。主题差异通过 CSS 变量（如 `--tag-bg`）而非硬编码选择器实现。
- **Token 驱动主题原则**：新增组件颜色如需主题差异化，必须在 `base/tokens.css` 定义语义变量，在各主题文件赋值，组件代码只消费变量，禁止写死 `[data-theme="xxx"]` 选择器。
- **白名单单一来源原则**：管理页 hash 白名单必须集中在单一常量模块（如 `constants.js`），`tabs/bootstrap` 统一引用，禁止多处硬编码。
- **自动刷新 URL 复用原则**：自动刷新容器的查询参数拼装必须复用同一工具函数（如 `buildAutoRefreshUrl`），避免不同模块行为漂移。
- **加载态复用原则**：按钮加载态统一复用 `utils.setButtonLoading`，禁止在 `bootstrap/filters/plans` 重复实现同名逻辑。
- **Bootstrap 职责拆分原则**：`bootstrap.js` 仅保留初始化与事件绑定；动作分发、相对时间、偏好状态、交换卡牌交互必须拆到独立模块，避免单文件膨胀。
- **事件绑定归口原则**：全局 `click/change/input/submit/htmx` 监听统一放在 `event_bindings.js`，`bootstrap.js` 仅调用绑定入口，避免初始化与事件细节耦合。
- **页面模块分层原则**：页面专属逻辑统一放在 `modules/features/`，根目录 `modules/` 仅保留编排、共享能力与跨页面路由/状态模块。
- **筛选分层原则**：筛选逻辑按 `records/owned/tasks` 拆分到 `modules/features/filters/`，通用表单序列化能力放在 `shared_form.js`，禁止再次回退到单文件混写。
- **显式依赖原则**：模块内禁止依赖 `window` 上的同名全局函数兜底（如 `isElementInActiveTab`），必须显式 `import` 保证可维护与可测试。
- 调试（chrome-devtools）时没有特别说明时端口一般在8000

## UI 设计决策记录

### 表格内容展示原则

- **计划配置页面**：不喜欢滚动，希望直接展示出来，滚动不方便
