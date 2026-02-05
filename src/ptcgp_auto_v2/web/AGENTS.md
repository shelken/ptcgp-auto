# Web 模块代码结构

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
│   └── pack_config.py
├── services/                   # 业务层（视图模型/业务组合）
│   ├── index_service.py
│   ├── record_service.py
│   ├── owned_card_service.py
│   ├── task_service.py
│   ├── plan_service.py
│   ├── metadata_service.py
│   ├── pack_config_service.py
│   └── account_service.py
├── queries/                    # 查询层（SQL 构造/分页过滤）
│   ├── record_queries.py
│   ├── owned_card_queries.py
│   ├── task_queries.py
│   └── metadata_queries.py
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
│       ├── main.js            # 主 JS 入口
│       └── modules/           # ES6 模块
│           ├── bootstrap.js   # 初始化与事件绑定
│           ├── card_preview.js # 卡牌预览
│           ├── filters.js     # 筛选/持久化
│           ├── tabs.js        # Tab 切换
│           ├── custom_select.js # 自定义下拉
│           ├── plans.js       # 计划列表
│           ├── tasks.js       # 任务排序与间隔
│           ├── owned_cards.js # 已拥有卡牌
│           ├── modal.js       # 模态框处理
│           └── utils.js       # 工具函数（toast、throttle、debounce 等）
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
  - `main.js`: 主入口，导入各模块
  - `modules/modal.js`: 模态框显示/隐藏逻辑
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
- **Tooltip**：优先使用 `data-tooltip` + 自定义样式，避免依赖浏览器原生 title 在主题/样式下不可见。
- **筛选条件缓存**：所有列表页面的筛选条件必须缓存（如 localStorage），避免刷新/切换后需要重新选择；恢复时注意不要触发重复请求。
- **筛选统一策略**：所有带筛选的列表页面必须使用统一的序列化/恢复逻辑（`serializeFormFilters`/`applyFormFilters`/`buildQueryParts`），避免各页面各写一套。
- **自定义 Select 初始化兜底**：HTMX/动态插入 DOM 后需确保自定义 Select 被自动初始化（可使用 MutationObserver 兜底），防止退回浏览器默认样式。
- **相对时间更新**：筛选/分页追加后要重新更新相对时间；`updateRelativeTimes` 需要能处理根节点与其最近容器。
- **相对时间展示一致**：所有列表中的时间字段统一使用“相对时间 + 悬浮具体时间”，并在 HTMX 替换后重算，避免筛选后回退成绝对时间。
- **关联预加载原则**：跨线程/跨会话使用 ORM 对象时，必须显式预加载所需关联，避免脱离 session 后数据缺失。
- **筛选恢复请求冲突**：恢复筛选仅回填 UI，不主动触发请求；首次加载由入口请求负责，避免“默认请求 + 恢复请求”双发。
- **隐藏区域请求隔离**：HTMX 触发前需检查当前 Tab/容器是否激活，避免隐藏区域误触发请求。
- 调试（chrome-devtools）时没有特别说明时端口一般在8000
