# Web 模块全景 Onboarding

## 技术栈

| 层 | 技术 | 版本/说明 |
|---|---|---|
| 后端框架 | FastAPI | HTMX 驱动，返回 HTML 片段而非 JSON |
| 模板 | Jinja2 | 单页应用 `index.html` + 20+ partials |
| 前端交互 | HTMX 1.9.10 | 局部页面更新、表单提交、无限滚动 |
| CSS | Tailwind (CDN) + 自定义 CSS 变量 | 8 套主题、34 个 design tokens |
| JS | ES6 Modules | 无构建工具，原生 `import/export` |
| 其他依赖 | SortableJS, Marked.js, DOMPurify | 拖拽排序、Markdown 渲染、XSS 防护 |
| 数据库 | SQLite + SQLModel/SQLAlchemy | ContextVar 管理 session |
| i18n | 2 语言 (en / zh_CN) | ~440 个翻译 key，flat JSON |

## 架构分层

```
Request
  │
  ▼
app.py (中间件: 语言检测 → ContextVar)
  │
  ▼
routers/ (参数解析 + 响应拼装)        ← 13 个路由模块, ~50 个端点
  │
  ▼
services/ (视图模型组装)              ← 14 个 service, ORM→dict 转换
  │
  ▼
queries/ (SQL 构造 + 分页)            ← 8 个 query 模块
  │
  ▼
db/repositories/ + db/models/         ← 核心数据层
```

**写操作模式**: Router 解析表单 → Service 调用 domain service/repository → Router 重新渲染列表 partial → `HX-Trigger` 头发送 toast/closeModal。

## 前端架构

### JS 模块结构（`static/js/modules/`）

```
main.js → bootstrap.initApp()
             │
             ├── initLang()                    语言同步
             ├── initTheme()                   主题恢复
             ├── restoreAllFilterCaches()       筛选缓存恢复
             ├── bindAppEventHandlers()         全局事件绑定
             │     └── event_bindings.js        统一事件中心
             │           ├── click → action_handlers.js (data-action 分发, ~25 种动作)
             │           ├── htmx:load          内容加载后初始化组件
             │           ├── htmx:afterSwap     modal 打开 + 状态同步
             │           ├── change/input       筛选缓存保存
             │           └── visibility/focus   自动刷新触发
             ├── restoreTab()                   Tab/hash 恢复
             └── 组件初始化                     custom select, 日期选择器...
```

### 关键设计模式

- **`data-action` 委托**：模板零内联事件，全部通过 `data-action` 属性 + `action_handlers.js` 统一分发
- **筛选缓存**：`shared_form.js` 统一管理 localStorage 读写，`data-filter-cache-key` 驱动
- **自动刷新**：`data-auto-refresh` 容器在 focus/visibility 变化时节流刷新
- **Modal**：`ModalManager` 单例，`hx-target="#modal-content"` + `htmx:afterSwap` 自动打开

## 页面结构

### 3 个主 Tab

| Tab | Hash | 内容 |
|---|---|---|
| Records | `#records` | 开包记录，卡片网格/列表视图，rarity/card_type 筛选，无限滚动 |
| Owned Cards | `#owned-cards` | 拥有卡牌网格，左侧多维筛选（账号/稀有度/类型/系列/包/元素），可调列数 |
| Management | `#management` | 9 个子页面，左侧导航栏切换 |

### Management 子页面（hash 白名单在 `constants.js`）

| 子页面 | 路由 | 功能 |
|---|---|---|
| accounts | `/management/accounts` | 账号管理、编辑、计划关联、开包配置 |
| plans | `/management/plans` | 任务计划 CRUD，拖拽排序任务类型 |
| resources | `/management/resources` | 资源统计 + 系列点数表 |
| tasks | `/management/tasks` | 任务实例列表，状态/类型/账号筛选，重置已完成 |
| metadata | `/management/metadata` | 元数据同步控制台，3 步向导（选择→预览→执行） |
| daily-gift | `/management/daily-gift` | 每日送卡记录、配对状态、日期选择器 |
| friendships | `/management/friendships` | 好友请求/关系管理 |
| exchange-cards | `/management/exchange-cards` | 交换卡牌请求管理 |
| notifications | `/management/notifications` | 通知配置（场景/webhook）+ 通知列表 |

## CSS 主题系统

8 套主题通过 `[data-theme]` 属性切换，所有样式消费 CSS 变量：

| 主题 | 风格 | 亮/暗 |
|---|---|---|
| **brutalist** (默认) | 粗线条、高对比、直角 | Light |
| organic | 自然 | Light |
| luxury | 深色金边 | Light |
| editorial | 杂志风 | Light |
| pastel | 柔粉圆角 | Light |
| retro | 复古未来 | Dark |
| art_deco | 几何装饰 | Dark |
| playful | 活泼彩色 | Dark |

## 模板宏（可复用组件）

| 宏 | 用途 |
|---|---|
| `data_table_card` | 管理表格外壳 |
| `data_table_toolbar_layout` | 双区工具栏（左/右） |
| `data_table_sort_button` | 排序列头 |
| `data_table_pager` / `pager_row` | 分页组件 |
| `modal_header` / `footer` / `container` | Modal 结构 |
| `input_field` / `textarea_field` / `select_field` | 表单控件 |
| `status_chip` | 统一状态标签（自动 tone + tooltip） |
| `auto_refresh_container` | 自动刷新容器 |
| `table_container` | 响应式表格 |

## 开发核心规范速查

1. **颜色**：禁止硬编码 `bg-white` 等，必须用 `.bg-theme` / `.bg-card` 等工具类
2. **事件**：禁止模板内联 `onclick`，用 `data-action` + `action_handlers.js`
3. **筛选**：统一走 `shared_form.js` 的 `data-filter-cache-key` 机制
4. **Modal**：走 `hx-target="#modal-content"` + `openFromSwap()` 自动打开
5. **i18n**：所有文本必须本地化，同步更新两个 locale JSON
6. **缓存版本**：改 CSS/JS 后更新 `index.html` 的 `?v=` 参数
7. **测试**：放 `web/tests/` 下，镜像源码结构，必须用内存数据库
8. **新增功能流程**：router → service → query → partial → macro → locale → JS module → 版本号

## 端点清单

### index.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/` | 渲染主页 |

### records.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/records` | 分页开包记录列表 |

### owned_cards.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/owned-cards` | 分页拥有卡牌网格 |
| GET | `/api/owned-cards/modal` | 卡牌详情 modal |
| GET | `/api/owned-cards/modal/exchange-accounts` | modal 内交换账号表 |
| POST | `/api/exchange-cards/requests` | 创建交换请求 |

### tasks.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/tasks` | 任务管理页 |
| GET | `/api/tasks` | 分页任务列表 |
| POST | `/api/tasks/reset-completed` | 重置已完成任务 |
| GET | `/management/tasks/reset-completed-modal` | 重置确认 modal |
| GET | `/management/tasks/{id}/target-pack` | 单任务目标包 |
| GET | `/api/tasks/account-options` | 账号搜索选项 |

### management.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/accounts` | 账号管理列表 |
| GET | `/management/accounts/{id}/target-pack` | 单账号目标包 |
| GET | `/management/accounts/{id}/edit` | 编辑账号 modal |
| POST | `/api/accounts/{id}/details` | 更新账号信息 |

### plans.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/plans` | 计划列表 |
| GET | `/management/plans/edit` | 计划编辑 modal |
| POST | `/api/plans` | 创建/更新计划 |
| DELETE | `/api/plans/{id}` | 删除计划 |
| GET | `/management/accounts/{id}/plans` | 账号计划关联 modal |
| POST | `/api/accounts/{id}/plans` | 更新账号计划关联 |

### metadata.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/metadata` | 元数据管理页 |
| POST | `/api/metadata/sync/preview` | 同步预览 |
| POST | `/api/metadata/sync/execute` | 执行同步 |
| POST | `/api/metadata/sync/check` | 刷新统计 |
| POST | `/api/metadata/node/select` | 选择节点 |

### pack_config.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/card-sets` | 卡组列表 JSON |
| GET | `/api/card-sets/{code}/boosters` | 子包列表 JSON |
| GET | `/management/accounts/{id}/pack-config` | 开包配置 modal |
| GET | `/partials/boosters-options` | 子包选项 HTML |
| POST | `/api/accounts/{id}/pack-config` | 保存开包配置 |

### friendship.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/friendships` | 好友管理页 |
| POST | `/api/friendships/requests/add` | 添加好友请求 |
| POST | `/api/friendships/requests/delete` | 删除好友请求 |
| POST | `/api/friendships/requests/{id}/cancel` | 取消请求 |

### daily_gift.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/daily-gift` | 每日送卡页 |

### exchange_card.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/exchange-cards` | 交换管理页 |
| POST | `/api/exchange-cards/requests/{id}/cancel` | 取消交换请求 |

### notifications.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/notifications` | 通知管理页 |
| GET | `/management/notifications/list` | 通知列表片段 |
| GET | `/notifications/count` | 未读徽标 |
| GET | `/notifications/recent` | 最近通知 |
| GET | `/management/notifications/card-picker-modal` | 卡牌选择器 modal |
| POST | `/management/notifications/card-picker/apply` | 应用卡牌选择 |
| POST | `/management/notifications/mark-read` | 标记已读 |
| POST | `/management/notifications/mark-all-read` | 全部已读 |
| POST | `/management/notifications/config` | 更新通知配置 |
| POST | `/management/notifications/test-webhook` | 测试 webhook |
| GET | `/notifications/panel` | 通知面板内容 |
| GET | `/notifications/load-more` | 面板加载更多 |
| POST | `/notifications/panel/mark-all-read` | 面板全部已读 |

### resources.py
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/management/resources` | 资源管理页 |
