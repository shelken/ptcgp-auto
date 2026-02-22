# Coding Conventions

**Analysis Date:** 2026-02-23

## Naming Patterns

**Files:**
- Python 文件使用 `snake_case`：`task_base.py`, `account_repository.py`
- 模块目录使用 `snake_case`：`tasks/`, `services/`, `repositories/`
- 测试文件使用 `test_*.py` 前缀：`test_daily_gift_service.py`
- Jinja2 模板使用 `snake_case.html`：`account_list.html`, `edit_account.html`

**类:**
- 使用 `PascalCase`：`OpenPackTask`, `AccountRepository`, `FriendshipService`
- 抽象基类不带前缀：`Task`, `Hook`
- Repository 类以 `Repository` 结尾：`AccountRepository`, `TaskInstanceRepository`
- Service 类以 `Service` 结尾：`FriendshipService`, `ExchangeCardService`
- 模型类使用领域名称：`Account`, `TaskInstance`, `PackRecord`

**函数与方法:**
- 使用 `snake_case`：`is_completed()`, `handle_page()`, `get_by_id()`
- 私有方法以 `_` 前缀：`_handle_home()`, `_is_action_done()`, `_mark_action_done()`
- 工厂方法使用 `@classmethod`：`TaskResult.ok()`, `TaskResult.fail()`, `TaskResult.skip()`
- 布尔返回方法以 `is_`, `has_`, `should_`, `was_` 开头：`is_completed()`, `is_friend()`, `should_stop()`

**变量:**
- 使用 `snake_case`：`task_type`, `account_id`, `pack_code`
- 私有实例变量以 `_` 前缀：`_account`, `_handlers`, `_action_cache`
- 常量使用 `UPPER_SNAKE_CASE`：`MAX_TASK_ITERATIONS`, `DEFAULT_WAIT_SECONDS`, `HOME_CHECK_THRESHOLD`

**类型:**
- 类型别名使用 `PascalCase`：`Recognizer = tuple[OcrEngine, TemplateMatcher]`
- 泛型使用 `list[dict]`, `dict[str, Any]` 等 Python 3.10+ 语法

## Code Style

**格式化:**
- 无独立格式化工具配置文件（依赖团队约定）
- 使用 4 空格缩进
- 行长度无强制限制，但保持可读性

**Linting:**
- 无独立 linting 配置文件
- 使用类型注解增强代码质量

**文件头:**
- 所有 Python 文件以 `# -*- coding: utf-8 -*-` 开头
- 模块级文档字符串使用中文描述用途：

```python
# -*- coding: utf-8 -*-
"""
任务基类与注册表模块

定义可插拔任务的接口规范和注册机制。
"""
```

**类文档:**
- 类必须有文档字符串，使用中文描述：
```python
class Task(ABC):
    """
    任务基类

    所有可插拔任务必须继承此类并实现抽象方法。
    任务采用「目标驱动 + 页面响应」的执行模式：
    - 目标驱动：任务知道自己的完成条件
    - 页面响应：根据当前页面执行相应动作
    """
```

**方法文档:**
- 公共方法必须有文档字符串：
```python
def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
    """处理识别到的页面"""
```

- 复杂方法需包含 Args 和 Returns：
```python
def bind_account(self, account: "Account"):
    """
    绑定执行账号

    Args:
        account: 账号模型实例
    """
```

## Import Organization

**顺序:**
1. 标准库（`import logging`, `from typing import ...`）
2. 第三方库（`from sqlmodel import ...`, `import uiautomator2 as u2`）
3. 项目内部模块（`from ptcgp_auto_v2.core import ...`）

**分组示例:**
```python
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

from ptcgp_auto_v2.config.constants import (
    PACK_AUTO_EXCLUDE_SET_CODES,
    PACK_SERIES_CODES,
)
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account
```

**路径导入:**
- 使用绝对导入：`from ptcgp_auto_v2.db.models import Account`
- 使用 `TYPE_CHECKING` 进行循环导入避免

## Error Handling

**模式:**
- 使用 `ActionResult` 返回操作结果而非抛异常：
```python
# 成功
return ActionResult.ok(wait=1.0)

# 失败
return ActionResult.fail("截图失败")
```

- 使用 `TaskResult` 返回任务结果：
```python
# 成功
return TaskResult.ok(iterations=10)

# 失败
return TaskResult.fail("超过最大迭代次数", iterations=100)

# 跳过
return TaskResult.skip(reason="未配置开包目标")
```

**异常处理:**
- 关键操作使用 `try/except` 并记录日志：
```python
try:
    cards = self.card_recognizer.scan_pack_result(set_code)
except RuntimeError as e:
    logger.error(f"识别卡牌失败: {e}")
    cards = []
```

- 连接失败等场景返回布尔值而非抛异常：
```python
def connect(self) -> bool:
    try:
        self.device = u2.connect(self.address)
        return True
    except (RuntimeError, ConnectionError, OSError) as e:
        logger.error(f"u2 连接失败: {e}")
        return False
```

**运行时检查:**
- 使用 `RuntimeError` 表示程序状态错误：
```python
if self._account is None:
    raise RuntimeError("任务未绑定账号")
```

- 使用 `ValueError` 表示参数错误：
```python
if task_type not in cls._tasks:
    raise ValueError(f"未知的任务类型: {task_type}")
```

## Logging

**框架:** Python 标准库 `logging`

**模式:**
```python
import logging
logger = logging.getLogger(__name__)
```

**日志级别使用:**
- `logger.debug()`: 详细调试信息（如流程步骤、变量值）
- `logger.info()`: 关键业务事件（如任务完成、账号创建）
- `logger.warning()`: 可恢复的异常情况（如未找到模板、自动回退）
- `logger.error()`: 需要关注的错误（如连接失败、识别失败）

**格式化:**
- 使用 `%s` 风格格式化（非 f-string）：
```python
logger.info("已连接设备: %s", self.address)
logger.warning("ADB 连续失败次数: %s/%s (%s)", failures, threshold, self.address)
```

**何时记录:**
- 任务开始/完成：`on_start()`, `on_complete()`
- 外部调用结果：ADB 连接、OCR 识别、HTTP 请求
- 业务决策点：跳过原因、自动选择、配置加载

## Comments

**何时注释:**
- 模块开头必须有中文文档字符串
- 类必须有中文文档字符串
- 公共方法必须有文档字符串
- 复杂逻辑块前加 `#` 注释说明意图
- 常量定义后加注释说明来源/用途

**页面规则注释原则:**
每个页面规则块前必须添加对应的中文注释：
```python
# 商店 / 得卡挑戰
{
    "name": "game_home_main",
    "identifiers": get_text_patterns("game_home_main"),
    ...
}
```

**JSDoc/TSDoc:**
- Python 使用标准 docstring，无 JSDoc

**禁止事项:**
- 不要随意清除原有的中文注释
- 不要硬编码 OCR 出来的文字内容，必须使用 locales 配置

## Function Design

**大小:**
- 原则上单个方法不超过 50 行
- 单个文件原则上最多不超过 500 行
- 超出时考虑拆分为 utils 模块或独立服务

**参数:**
- 使用类型注解：`def handle_page(self, page_name: str, page_info: dict) -> ActionResult`
- 可选参数使用 `Optional[T]` 和默认值：`now: Optional[datetime] = None`
- 复杂参数使用 dataclass 封装

**返回值:**
- 使用 `ActionResult` / `TaskResult` 封装结果
- 布尔返回用于简单判断：`is_completed() -> bool`
- None 表示未找到或失败：`get_by_id() -> Optional[Account]`

## Module Design

**导出:**
- 使用 `__init__.py` 暴露公共接口：
```python
from ptcgp_auto_v2.db.models import Account, TaskInstance
__all__ = ["Account", "TaskInstance"]
```

**Barrel Files:**
- `db/models/__init__.py` 导出所有模型
- `db/repositories/__init__.py` 导出所有仓储
- `tasks/__init__.py` 导出任务类

**模块职责:**
- `core/`: 核心调度逻辑（不涉及业务细节）
- `tasks/`: 任务实现（业务逻辑）
- `infra/`: 基础设施（ADB、OCR、模型管理）
- `services/`: 业务服务层（跨任务复用逻辑）
- `db/`: 数据访问层（模型 + 仓储）
- `web/`: Web UI（FastAPI + HTMX）

---

*Convention analysis: 2026-02-23*
