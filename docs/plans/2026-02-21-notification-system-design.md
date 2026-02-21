# 通知系统设计文档

## 概述

实现站内通知 + 企业微信 Webhook 通知系统，支持多场景配置，用于任务状态、稀有卡牌获取、系统警告等通知。

## 场景定义

| 场景名称 | 说明 | 可配置项 |
|---------|------|---------|
| `rare_card_obtained` | 获得稀有卡牌 | 启用开关 + 稀有度列表 + 具体卡牌ID列表 |
| `task_status` | 任务执行结果 | 启用开关 + task_type 列表 + 失败/异常开关 |
| `system_warning` | 系统级警告 | 启用开关 |

### `rare_card_obtained` 配置结构

```json
{
  "notify_by_rarity": ["R", "RR"],
  "notify_card_ids": [123, 456, 789]
}
```

**触发逻辑：**
1. 检查卡牌 ID 是否在 `notify_card_ids` 中 → 是 → 通知
2. 检查卡牌稀有度是否在 `notify_by_rarity` 中 → 是 → 通知
3. 都不满足 → 不通知

### `task_status` 配置结构

```json
{
  "notify_task_types": ["open_pack", "exchange_cards", "send_card_daily"],
  "notify_on": ["failed", "blocked", "timeout"]
}
```

**可选状态：**
- `failed` - 任务失败
- `blocked` - 任务阻塞
- `timeout` - 任务超时
- `success` - 任务成功（可选）

## 数据模型

### 通知记录表 `notification`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| scene | STRING | 场景名称 |
| title | STRING | 通知标题 |
| content | TEXT | Markdown 内容 |
| related_account_id | INTEGER | 关联账号（可选） |
| related_task_instance_id | INTEGER | 关联任务实例（可选） |
| is_read | BOOL | 已读状态，默认 False |
| created_at | DATETIME | 创建时间（本地时间） |

### 通知配置表 `notification_config`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| scene | STRING | 场景名称（唯一） |
| enabled | BOOL | 是否启用通知 |
| enabled_webhook | BOOL | 是否启用企微推送 |
| extra_config | JSON | 扩展配置 |

### 系统配置

通过环境变量或配置文件管理：

| 配置项 | 环境变量 | 说明 |
|--------|---------|------|
| webhook_url | `PTCGP_WEBHOOK_URL` | 企业微信 Webhook URL |

## 模块架构

```
src/ptcgp_auto_v2/
├── infra/
│   └── notifier.py              # 通知器核心实现
├── db/models/
│   ├── notification.py          # 通知记录模型
│   └── notification_config.py   # 通知配置模型
├── db/repositories/
│   ├── notification_repository.py     # 通知记录 DAO
│   └── notification_config_repository.py  # 通知配置 DAO
├── web/routers/
│   └── notifications.py         # 通知管理路由
└── web/templates/
    └── partials/
        ├── notification_page.html
        ├── notification_list.html
        ├── notification_config.html
        └── notification_config_item.html
```

## 核心类设计

### Notifier 类

```python
# infra/notifier.py

class Notifier:
    """统一通知入口"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
    
    def notify(
        self,
        scene: str,
        title: str,
        content: str,
        account_id: int = None,
        task_instance_id: int = None,
        image_url: str = None,
    ) -> None:
        """发送通知（站内 + 企微 Webhook）"""
        pass
    
    def notify_rare_card(
        self, 
        account, 
        card, 
        rarity: str,
        image_url: str = None
    ) -> None:
        """稀有卡牌通知（便捷方法）"""
        pass
    
    def notify_task_status(
        self, 
        task_instance, 
        status: str,
        message: str
    ) -> None:
        """任务状态通知（便捷方法）"""
        pass
    
    def notify_system_warning(
        self,
        title: str,
        message: str
    ) -> None:
        """系统警告通知（便捷方法）"""
        pass
```

### 调用示例

```python
# 在任务执行器中
notifier.notify_task_status(task_instance, "failed", "认证过期")

# 在开包任务中
notifier.notify_rare_card(account, card, "★★★", image_url="https://...")

# 系统警告
notifier.notify_system_warning("设备异常", "设备 5555 连接失败")
```

## 企业微信 Webhook

### 消息格式

使用 Markdown 类型：

```python
def _send_webhook(self, title: str, content: str, image_url: str = None):
    """发送企微 Webhook"""
    markdown_content = f"## {title}\n\n{content}"
    if image_url:
        markdown_content += f"\n\n![card]({image_url})"
    
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }
    requests.post(self.webhook_url, json=payload, timeout=5)
```

### 图片 URL 格式

使用现有 CDN 地址：

```
https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/{locale}/cards-by-set/{set_code}/{number}.png
```

### 通知内容示例

**稀有卡牌通知：**
```
## 稀有卡牌通知

账号 **Shelken** 开出 **★★★ 皮卡丘 ex**

![card](https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh_hant/cards-by-set/A1/001.png)
```

**任务状态通知：**
```
## 任务状态通知

账号 **Shelken** 开包任务 **失败**

**原因**: 认证过期，请重新登录

**时间**: 2026-02-21 10:30:00
```

### 失败处理

- Webhook 发送失败时记录日志，不影响主流程
- 超时设置：5 秒

## Web 管理界面

### 通知列表页

- 展示所有通知记录
- 支持按场景、账号筛选
- 支持标记已读/全部已读
- 分页展示

### 通知配置页

- 全局 Webhook URL 配置
- 每个场景的启用开关
- 场景特定配置：
- `rare_card_obtained`: 稀有度多选（数据库字母码）+ 卡牌点击选择器（Modal + owned-grid 排列 + 服务端分页 + 已选蒙版+勾图标）
  - `task_status`: task_type 多选 + 状态多选
  - `system_warning`: 仅启用开关

### 顶部通知图标

- 显示未读数量徽标
- 点击展开最近通知列表
- 快速跳转到通知列表页

## 实现步骤

**状态：已完成 ✅**

1. **数据模型** - 创建 `notification` 和 `notification_config` 模型 ✅
   - `src/ptcgp_auto_v2/db/models/notification.py`
   - `src/ptcgp_auto_v2/db/models/notification_config.py`
2. **Repository 层** - 实现数据访问 ✅
   - `src/ptcgp_auto_v2/db/repositories/notification_repository.py`
   - `src/ptcgp_auto_v2/db/repositories/notification_config_repository.py`
3. **Notifier 核心** - 实现通知发送逻辑 ✅
   - `src/ptcgp_auto_v2/infra/notifier.py`
4. **Webhook 集成** - 实现企微推送 ✅（集成在 Notifier 中）
5. **Web 路由** - 实现通知列表和配置接口 ✅
   - `src/ptcgp_auto_v2/web/routers/notifications.py`
6. **前端页面** - 实现通知列表、配置页面 ✅
   - `src/ptcgp_auto_v2/web/templates/partials/notification_list.html`
   - `src/ptcgp_auto_v2/web/templates/partials/notification_config.html`
7. **任务集成** - 在任务执行器中集成通知调用 ✅
   - `src/ptcgp_auto_v2/core/executor.py` - 任务状态通知
   - `src/ptcgp_auto_v2/tasks/open_pack.py` - 稀有卡牌通知

## 重构进展（2026-02-21）

在保持现有功能与接口行为不变的前提下，完成通知系统代码区的一次“去重复 + 复用化”重构：

1. **Router 参数归一化复用** ✅
   - 抽取 `_parse_is_read_filter`，统一 `is_read` 布尔解析逻辑，避免多个路由重复写同样分支。
   - 抽取 `_parse_unique_int_ids`，统一卡牌 ID 解析、去重、非法值过滤逻辑。
   - 抽取 `_render_notification_page`，统一通知页面/列表上下文构建与模板渲染，减少重复参数拼装。

2. **Notifier 条件判断与文案生成复用** ✅
   - 抽取 `_is_rare_card_notifiable` 与 `_is_task_status_notifiable`，将通知条件判断集中，提升可维护性。
   - 抽取 `_resolve_account_name` 与 `_format_now`，统一账号名解析和时间格式输出。
   - 提取任务状态中文映射常量 `TASK_STATUS_TEXT_MAP`，避免方法内散落字典。

3. **测试补强（先红后绿）** ✅
   - 新增 Router 复用助手测试：
     - `test_parse_is_read_filter_values`
     - `test_parse_unique_int_ids_deduplicates_and_skips_invalid`
   - 全量回归通知相关测试通过：
     - `src/ptcgp_auto_v2/web/tests/routers/test_notifications.py`（10 passed）
     - `src/ptcgp_auto_v2/tests/infra/test_notifier.py`（16 passed）

## 重构进展（2026-02-21 第二轮）

继续在“功能不变”的前提下，扩大复用重构覆盖面：

1. **通知列表过滤参数单入口** ✅
   - 在 `notifications router` 新增 `_build_notification_list_filters`，统一处理：
     - scene 合法化
     - account_id 容错解析
     - is_read 字符串转布尔
     - page/page_size 边界约束
   - 所有通知列表相关路径（页面渲染、全部已读、测试发送选取首条通知）统一复用该入口，避免同类逻辑再次散落。

2. **通知上下文构建复用** ✅
   - 新增 `_build_notifications_page_context`，统一将归一化后的 filters 转换为 `build_notifications_context` 参数。
   - `get_notifications_page` / `get_notifications_list` / `send_test_webhook` 走同一上下文构建路径。

3. **Notifier 文案与配置读取抽象** ✅
   - 新增 `_load_scene_extra_config`，统一读取“场景启用状态 + extra_config”。
   - 新增 `_build_rare_card_content`、`_build_task_status_content`、`_build_system_warning_content`，统一正文拼装。
   - 新增 `_build_webhook_payload`，统一 markdown/markdown_v2 负载构建逻辑。

4. **第二轮 TDD 回归** ✅
   - 新增测试：
     - `test_build_notification_list_filters_normalizes_values`
     - `test_build_webhook_payload_without_image_uses_markdown`
     - `test_build_webhook_payload_with_image_uses_markdown_v2`
   - 回归通过：
     - `src/ptcgp_auto_v2/web/tests/routers/test_notifications.py`（11 passed）
     - `src/ptcgp_auto_v2/tests/infra/test_notifier.py`（18 passed）

## 重构进展（2026-02-21 第三轮）

在“继续全量去重复”的要求下，完成通知模块的**跨层常量与默认配置单一来源化**：

1. **新增通知共享配置模块** ✅
   - 新增 `src/ptcgp_auto_v2/config/notification.py`，集中管理：
     - 场景常量（`SCENE_RARE_CARD` 等）
     - 场景列表与 i18n key 映射
     - 任务类型/任务状态选项
     - 卡图 CDN Base URL
     - 场景默认配置构建函数 `build_default_scene_config`

2. **Repository 默认配置去硬编码** ✅
   - `notification_config_repository.py` 改为复用 `NOTIFICATION_SCENE_OPTIONS` 与 `build_default_scene_config`。
   - 删除 repository 内部重复 defaults 字典，避免后续改一处漏三处。

3. **Service / Router / Notifier 常量统一来源** ✅
   - `notification_service.py` 改为复用共享场景与任务选项，`_build_scene_options` 基于映射动态组装。
   - `notifications.py` 改为复用共享场景常量与统一卡图 CDN 常量。
   - `infra/notifier.py` 改为复用共享场景常量与统一卡图 CDN 常量。

4. **跨模块重复常量再收敛** ✅
   - `utils/image_manager.py` 的 CDN base URL 改为复用通知共享配置，避免再次出现同一 URL 多处硬编码。

5. **第三轮 TDD 回归** ✅
   - 新增测试文件：`src/ptcgp_auto_v2/tests/config/test_notification_constants.py`
   - 新增测试点：
     - 场景顺序稳定
     - 默认配置复用项目级默认常量
     - 默认配置返回深拷贝（无共享可变对象）
   - 回归通过：
     - `src/ptcgp_auto_v2/tests/config/test_notification_constants.py`（3 passed）
     - `src/ptcgp_auto_v2/web/tests/services/test_notification_service.py`（5 passed）
     - `src/ptcgp_auto_v2/tests/db/test_notification_config_repository.py`（14 passed）
     - `src/ptcgp_auto_v2/web/tests/routers/test_notifications.py`（11 passed）
     - `src/ptcgp_auto_v2/tests/infra/test_notifier.py`（18 passed）

## 重构进展（2026-02-21 第四轮）

针对“下载器不应引用通知语义常量”的问题，完成跨模块语义解耦：

1. **提取通用资源常量模块** ✅
   - 新增 `src/ptcgp_auto_v2/config/assets.py`。
   - 将卡图 CDN 根地址迁移为通用常量 `CARD_IMAGE_CDN_BASE_URL`。

2. **移除通知语义对通用资源的承载** ✅
   - `config/notification.py` 不再定义卡图 CDN 常量，仅保留通知领域配置。

3. **引用关系修正** ✅
   - `utils/image_manager.py`、`web/routers/notifications.py`、`infra/notifier.py` 全部改为直接引用 `config/assets.py`，避免“通用模块依赖通知模块”的语义反向耦合。
