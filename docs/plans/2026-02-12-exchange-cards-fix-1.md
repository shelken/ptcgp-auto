# Exchange Cards Web UI Fix Plan

> **原始需求**: @docs/needs/11-交换卡牌.md
> **关联计划**: @docs/plans/2026-02-12-exchange-cards.md

## 问题背景

完成 Task 1-7 后，发现 Web 页面与需求有多处不一致：

### 1. 换卡入口弹窗问题

| 需求 | 当前实现 | 问题 |
|------|---------|------|
| 要有能够过滤账号的搜索框 | 无搜索框 | **缺失** |
| 左边卡牌要小点，不对半分 | `grid md:grid-cols-2` 左右对半 | **布局不对** |
| 卡��支持拖拽旋转查看（同抽卡记录） | 静态图片 | **缺失交互** |
| 点击后输入 friend_id | 直接用 `item.friend_id` | **没有输入框** |
| 需要用户确认赠送 | 直接提交表单 | **没有确认步骤** |
| 检查账号是否有活跃请求 | 未检查 | **前置校验缺失** |

### 2. 服务层校验缺失

`ExchangeCardService.create_request()` 没有检查：
- 账号是否有 `sending` 或 `sended` 状态的活跃请求
- 需求明确：**每次一个账号只有一个 request 在运行**

---

## Task 1: 服务层添加活跃请求校验

**Files:**
- Modify: `src/ptcgp_auto_v2/services/exchange_card_service.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`

**实现内容:**
1. 在 `ExchangeCardRequestRepository` 添加 `has_active_request(account_id)` 方法
2. 在 `ExchangeCardService.create_request()` 中调用检查，存在活跃请求时返回 None

---

## Task 2: 弹窗布局调整（左小右大）

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`

**实现内容:**
1. 改为左 1/3 右 2/3 布局（或 flex 比例）
2. 左侧卡牌区域缩小，保留图片预览

---

## Task 3: 账号搜索框

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
- Modify: `src/ptcgp_auto_v2/web/static/js/main.js`（版本号）
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`

**实现内容:**
1. 在账号列表上方添加搜索输入框
2. 实现前端实时过滤账号列表
3. 使用 `data-action` 事件委托

---

## Task 4: 卡牌拖拽旋转预览

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
- Modify: `src/ptcgp_auto_v2/web/static/css/main.css`（如需样式）
- Modify: `src/ptcgp_auto_v2/web/static/js/main.js`（版本号）

**实现内容:**
1. 复用 `card_preview.js` 的拖拽旋转逻辑
2. 在弹窗卡牌上添加 `card-preview` 类和相关属性
3. 添加提示文字「拖动旋转查看」

---

## Task 5: 交互流程改造（输入 friend_id + 确认）

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
- Modify: `src/ptcgp_auto_v2/web/services/owned_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`

**实现内容:**
1. 点击账号行 → 展开输入区域（friend_id 输入框 + 确认按钮）
2. 默认填充已有 friend_id（如有）
3. 确认按钮点击后提交请求
4. 添加账号活跃请求状态展示（如有活跃请求则禁用按钮）

---

## Task 6: 本地化与版本更新

**Files:**
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Modify: `src/ptcgp_auto_v2/web/templates/index.html`（CSS/JS 版本号）

**新增翻译键:**
- `exchange_search_accounts`: 搜索账号
- `exchange_input_friend_id`: 输入目标 Friend ID
- `exchange_confirm_send`: 确认发送
- `exchange_has_active_request`: 该账号有进行中的交换请求
- `exchange_card_preview_hint`: 拖动旋转查看

---

## 执行顺序

1. Task 1（服务层校验）- 后端基础
2. Task 2（布局调整）- 基础结构
3. Task 4（卡牌旋转）- 独立功能
4. Task 3（账号搜索）- 独立功能
5. Task 5（交互流程）- 依赖 Task 1 校验结果
6. Task 6（本地化）- 收尾

---

## 验证清单

- [x] IM/UR 稀有度弹窗显示「不可交换」
- [x] 账号有活跃请求时按钮禁用 + 提示
- [x] 搜索框可实时过滤账号
- [x] 卡牌可拖拽旋转查看
- [x] 点击账号展开输入区域
- [x] 输入 friend_id 后可提交
- [x] 所有文本有中英文翻译

## 已完成修改

### 文件变更清单

| 文件 | 变更内容 |
|------|---------|
| `owned_card_service.py` | 添加 `has_active_request` 状态查询 |
| `owned_card_detail.html` | 重构布局（左 1/3 右 2/3）、搜索框、交互流程、卡牌预览 |
| `bootstrap.js` | 添加搜索过滤、表单显示/隐藏、卡牌预览事件绑定 |
| `zh_CN.json` | 新增翻译键 |
| `en.json` | 新增翻译键 |
| `index.html` | CSS/JS 版本号更新 |
