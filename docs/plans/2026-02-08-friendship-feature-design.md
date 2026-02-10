# 好友关系功能实施计划

> **原始需求**: docs/needs/08-处理好友关系.md  
> **创建日期**: 2026-02-08  
> **关联 beads Feature**: beads-dq3 "处理好友关系功能"  
> **作者**: AI Assistant  
> **状态**: 实施中（Phase 1/2 已完成，Phase 3 进行中）

---

## 设计决策对话记录

以下记录设计过程中的关键对话原文和决策变更：

### 关键澄清

**关于删除好友的逻辑（用户原话）：**
> "并不是全量重置，而是需要检查好友关系表。我文档有写"

**正确理解：** 不是"全量重置"，而是"与好友关系表同步"：
1. 遍历游戏内的好友列表
2. 获取每个好友的 `friend_id`
3. 检查是否在 `account_friendship` 表中
4. **如果不在表中** → 删除该好友
5. **如果在表中** → 保留

**关于删除范围（用户确认）：**
> "只实现“同步删除”"

**正确理解：** 首版只支持 `to_friend_id` 为空的同步删除，不实现“指定好友删除”。

**关于Hook插入任务的机制（用户纠正）：**
> "直接复用原来那个insert task"
> "要有一个机制，让执行器转换任务"

**正确理解：** Hook返回`INSERT_TASK`时，需要：
1. Hook返回`(INSERT_TASK, {"task_type": "xxx", ...})`指定要插入的任务类型
2. 执行器检测到`INSERT_TASK`后，在当前批次队列开头插入指定的前置任务
3. 当前任务暂停（返回skip），等待前置任务完成后自动继续
4. **不是**Hook自己创建TaskInstance或更新状态，而是执行器负责创建和调度

**关于任务实现规范（用户要求）：**
> "肯定不能直接调用adb，而是必须使用gesture。"

**正确理解：** `ManageFriendshipTask` 页面处理必须遵循 `src/ptcgp_auto_v2/tasks/AGENTS.md`，使用 `gesture` 工具函数完成点击/输入，且页面内用 `action_cache` 记录已完成操作。

**关于 Hook 动态注入（用户要求）：**
> "pre 和 post 应该要根据任务执行状态来动态获取...每次执行器应该检查是否有pre和post，然后任务在流转执行过程中，往列表中插入。"

**正确理解：** Hook 不是初始化时固定绑定；执行器每次执行任务前应动态获取 pre/post，
并在任务流转过程中根据状态插入前置/后置任务。

**关于测试计划（用户要求）：**
> "测试计划也是需要跳过的，不要删除。"

**正确理解：** 保留“测试计划暂时跳过”的说明与注释块，后续实现完成再补测试。

**关于任务实现成熟度（用户补充）：**
> "代码并不是实际最终的，后续需要大量页面调试和调整，具体页面我还没处理，目前的task仅仅是demo级别"

**正确理解：** 设计文档中的 `ManageFriendshipTask` 代码仅为 Demo 级示例，后续需要结合真实页面进行大量调试与规则校准，当前页面识别与点击逻辑不视为最终实现。

**关于删除流程回退（用户澄清）：**
> "当点击ok之后，就会删除好友，之后页面会重新留在账号的详情页面，此时需要返回回到列表页面。"

**正确理解：** 删除确认后要从好友详情页返回到好友列表页，才能继续后续同步删除流程。

**关于 ManageFriendshipTask 目前阶段（用户确认）：**
> "从现在开始ManageFriendshipTask全部todo"

**正确理解：** `ManageFriendshipTask` 相关流程全部标注为 TODO，占位搭框架即可。

### 架构决策

**前置任务机制（用户确认）：**
> "确认使用 Hook 机制"

**具体实现方案（用户确认）：**
> "posthook之后，应该更新对应账号的taskinstance的status为pending，让调度器自动调度"

### 任务合并决策

**初始错误设计：** 三个独立任务（发送、接受、删除）

**最终决策：** 一个统一任务 `ManageFriendshipTask`，扫描表执行所有操作

### 外部账号处理（用户补充）：

> "当要加的好友不是系统账号id，而是仅有friendid时，发送方在发送之后直接将request改成完成状态，并维护好友关系表，因为外部账号，仅靠外部接受，我们默认视为完成好友关系。"

### 其他关键决策

| 决策项 | 用户原话/选择 | 说明 |
|--------|--------------|------|
| 唯一性约束 | "B 通过应用层检查当前是否已经有了相关的请求" | 应用层检查 + 数据库约束 |
| 删除后状态 | "物理删除" | friendship 表记录物理删除 |
| 错误重试 | "A" | 不重试，直接标记 failed |

### beads 任务结构变更

**初始错误结构（6个任务）：**
- beads-cli, beads-skd, beads-ug0, beads-epe, beads-88n, beads-x4a

**用户纠正后（3个任务）：**
- beads-cli: 数据库模型设计
- beads-x4a: Hook 机制实现（基础设施）
- beads-ug0: 管理好友关系任务（合并发送/接受/删除）

**删除的任务：**
- beads-skd: 状态机实现（简化为 Task 内直接更新）
- beads-epe: 接受好友请求任务（合并）
- beads-88n: 删除好友任务（合并）

---

## 一、需求概述

### 1.1 功能目标
实现 PTCGP 游戏内的好友关系管理功能，支持：
- **发送好友请求**（由账号 A 向账号 B 发起）
- **接受好友请求**（由账号 B 接受来自账号 A 的请求）
- **删除好友**（与数据库中的好友关系表同步）

### 1.2 任务性质
- **类型**: Once 任务（一次性任务）
- **触发方式**: 
  - 其他任务触发（如送卡牌任务前置检查）
  - 用户手动触发（管理页面操作）

### 1.3 关键设计决策

| 决策项 | 选择 | 原因 |
|--------|------|------|
| 任务合并 | **单一任务** | ManageFriendshipTask 统一处理发送、接受、删除 |
| 触发机制 | **数据库记录 + Hook** | 外部通过 FriendshipService 创建记录，Hook 更新 TaskInstance 触发调度 |
| 删除策略 | **仅同步删除（to_friend_id 为空）** | 首版仅支持按好友关系表同步 |
| 状态管理 | **Task 内直接更新** | 无需独立状态机 |
| 外部账号 | **发送后直接完成** | 外部账号无法感知接受状态，默认视为完成 |

---

## 二、数据库模型设计（beads-cli）

### 2.1 好友请求表 (account_friend_request)

```python
# src/ptcgp_auto_v2/db/models/account_friend_request.py

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class AccountFriendRequest(SQLModel, table=True):
    """
    好友请求表
    
    记录好友请求的完整生命周期。
    - add 类型: sending -> sended -> completed/failed
    - delete 类型: deleting -> completed/failed
    """
    
    __tablename__ = "account_friend_request"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 发送方（必须知道账号 ID）
    from_account_id: int = Field(index=True, description="发送方账号ID")
    
    # 接收方（可以是账号 ID 或 friend_id）
    to_account_id: Optional[int] = Field(
        default=None, 
        description="接收方账号ID（系统内账号）"
    )
    to_friend_id: Optional[str] = Field(
        default=None, 
        index=True,
        description="接收方friend_id（外部账号只有这个）"
    )
    
    # 请求类型: add(添加) / delete(删除)
    request_type: str = Field(default="add", description="add 或 delete")
    
    # 状态
    # add 类型: sending -> sended -> completed / failed
    # delete 类型: deleting -> completed / failed
    status: str = Field(default="sending", description="状态")
    
    # 失败原因
    failed_reason: Optional[str] = None
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

**状态说明:**

**add 类型请求（系统内账号）:**
```
sending ──发送成功──► sended ──对方接受──► completed
                              │
                              ▼
                         friendship表创建双向记录
```

**add 类型请求（外部账号）:**
```
sending ──发送成功──► completed
                     │
                     ▼
            friendship表创建记录(friend_account_id=null)
            （外部账号无法感知接受状态，默认视为完成）
```

**delete 类型请求（首版仅支持同步删除）:**
```
deleting ──删除成功──► completed
     │
     ▼
   failed
```

**索引设计:**
- `from_account_id`: 查询某账号发起的请求
- `to_account_id`: 查询某账号接收的请求（系统内）
- `to_friend_id`: 通过 friend_id 查询（外部账号）
- `status`: 按状态筛选

### 2.2 好友关系表 (account_friendship)

```python
# src/ptcgp_auto_v2/db/models/account_friendship.py

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class AccountFriendship(SQLModel, table=True):
    """
    好友关系表
    
    记录已建立的好友关系。
    双向关系需要两条记录（A→B 和 B→A）。
    """
    
    __tablename__ = "account_friendships"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 账号 A 的 ID
    account_id: int = Field(index=True, description="账号ID")
    
    # 账号 B 的 friend_id（游戏内可见）
    friend_id: str = Field(index=True, description="好友的friend_id")
    
    # 账号 B 的 account_id（如果 B 也是系统内账号，可选）
    friend_account_id: Optional[int] = Field(
        default=None,
        description="好友的账号ID（系统内账号有值）"
    )
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
```

**说明:**
- 允许 `friend_account_id` 为空，支持系统外账号
- 双向关系需要两条记录（A→B 和 B→A）
- 唯一约束: `(account_id, friend_id)`

---

## 三、Hook 机制设计（beads-x4a）

### 3.1 核心架构

```python
# src/ptcgp_auto_v2/core/hooks.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.device_pool import Device
    from ptcgp_auto_v2.core.executor import Executor
    from ptcgp_auto_v2.core.task_base import Task
    from ptcgp_auto_v2.db.models import Account


class HookResult(Enum):
    """Hook 执行结果"""
    CONTINUE = "continue"      # 继续执行主任务
    ABORT = "abort"            # 中断执行
    INSERT_TASK = "insert"     # 需要插入并执行前置任务，暂停当前任务


@dataclass
class HookContext:
    """
    Hook 执行上下文
    
    提供 Hook 所需的全部信息和操作能力。
    """
    device: "Device"           # 当前设备
    account: "Account"         # 当前账号
    task: "Task"              # 当前任务
    executor: "Executor"      # 执行器（用于 insert_task 等操作）


class Hook(ABC):
    """Hook 基类"""
    
    @abstractmethod
    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """
        执行 Hook 逻辑
        
        Args:
            context: 执行上下文
            
        Returns:
            (HookResult, data) 指示后续操作
            - HookResult.CONTINUE: data 为空
            - HookResult.ABORT: data 包含 error 信息
            - HookResult.INSERT_TASK: data 包含 task_type, priority 等
        """
        pass
```

### 3.2 Task 基类集成

```python
# src/ptcgp_auto_v2/core/task_base.py (修改)

class Task(ABC):
    """任务基类"""
    
    # 动态 Hook 由执行器/任务运行期获取，不在初始化时固定
    
    def execute(self) -> TaskResult:
        """执行任务主循环"""
        from ptcgp_auto_v2.core.hooks import HookResult
        
        self.on_start()
        
        # 动态获取 pre_hooks
        pre_hooks = self.get_pre_hooks()
        for hook in pre_hooks:
            result, data = hook.run(self._hook_context)
            
            if result == HookResult.ABORT:
                error_msg = data.get("error", "PreHook aborted")
                result = TaskResult.fail(error_msg)
                self.on_complete(result)
                return result
            
            if result == HookResult.INSERT_TASK:
                # 将任务类型等信息传递给执行器
                self._pre_task_data = data
                result = TaskResult.skip(
                    reason="Waiting for pre-task",
                    pre_task_type=data.get("task_type"),
                    pre_task_priority=data.get("priority", "high")
                )
                self.on_complete(result)
                return result
        
        # 执行主任务逻辑
        result = self._execute_main_loop()
        
        # 动态获取 post_hooks（无论主任务成功失败）
        post_hooks = self.get_post_hooks()
        for hook in post_hooks:
            hook.run(self._hook_context)
        
        self.on_complete(result)
        return result

    def get_pre_hooks(self) -> list["Hook"]:
        """动态获取前置 Hook（可基于任务/账号状态生成）"""
        return []

    def get_post_hooks(self) -> list["Hook"]:
        """动态获取后置 Hook（可基于任务/账号状态生成）"""
        return []
```

### 3.3 执行器支持

```python
# src/ptcgp_auto_v2/core/executor.py (修改)

class AccountBatchExecutor(BaseExecutor):
    """账号批量任务执行器"""
    
    def __init__(self, ...):
        super().__init__(...)
        self._hook_context: Optional[HookContext] = None
    
    def _build_hook_context(self, task: Task) -> HookContext:
        """构建 Hook 上下文"""
        return HookContext(
            device=self.device,
            account=self.account,
            task=task,
            executor=self
        )
    
    def _execute_single_task(self, task_instance: "TaskInstance"):
        """执行单个任务（支持 Hook）"""
        task = self._build_task(task_instance, self.account)
        
        # 设置 Hook 上下文
        task._hook_context = self._build_hook_context(task)
        
        # 执行任务（内部会处理 pre/post hooks）
        result = task.execute()
        
        # 检查是否需要插入前置任务
        if result.skipped and result.data.get("pre_task_type"):
            pre_task_type = result.data.get("pre_task_type")
            pre_task_priority = result.data.get("pre_task_priority", "high")
            
            # 获取或创建前置任务实例
            pre_task_instance = self._get_or_create_task_instance(
                account_id=self.account.id,
                task_type=pre_task_type
            )
            
            # 确保前置任务是 pending 状态
            if pre_task_instance.status != TaskStatus.PENDING.value:
                pre_task_instance.status = TaskStatus.PENDING.value
                pre_task_instance.save()
            
            # 插入到当前批次队列开头（优先执行）
            self.pending_tasks.insert(0, pre_task_instance)
            
            # 当前任务保持 running 状态，等待前置任务完成后自动继续
            return

        # 任务完成后，动态检查是否需要插入后置任务
        post_task_type = result.data.get("post_task_type") if result.data else None
        if post_task_type:
            post_task_instance = self._get_or_create_task_instance(
                account_id=self.account.id,
                task_type=post_task_type
            )
            if post_task_instance.status != TaskStatus.PENDING.value:
                post_task_instance.status = TaskStatus.PENDING.value
                post_task_instance.save()
            self.pending_tasks.insert(0, post_task_instance)
            return
        
        # 更新任务状态...
```

---

## 四、开放接口设计（beads-ug0 的一部分）

```python
# src/ptcgp_auto_v2/services/friendship_service.py

from typing import Optional
from ptcgp_auto_v2.db.repositories import (
    FriendRequestRepository,
    FriendshipRepository,
    TaskInstanceRepository,
)

class FriendshipService:
    """
    好友关系服务
    
    供 Hook 和外部任务调用的开放接口。
    通过创建数据库记录 + 触发 TaskInstance 来实现任务调度。
    """
    
    @staticmethod
    def create_add_request(
        from_account_id: int,
        to_friend_id: str,
        to_account_id: Optional[int] = None
    ) -> "AccountFriendRequest":
        """
        创建添加好友请求
        
        用于 FriendPreHook 或其他任务需要建立好友关系时调用。
        
        Args:
            from_account_id: 发送方账号ID
            to_friend_id: 接收方 friend_id
            to_account_id: 接收方账号ID（如果是系统内账号）
            
        Returns:
            创建的请求记录
        """
        # 1. 创建请求记录
        request = FriendRequestRepository().create(
            from_account_id=from_account_id,
            to_friend_id=to_friend_id,
            to_account_id=to_account_id,
            request_type="add",
            status="sending"
        )
        
        # 2. 触发 ManageFriendshipTask 调度
        TaskInstanceRepository().update_status_to_pending(
            account_id=from_account_id,
            task_type="manage_friendship"
        )
        
        return request
    
    @staticmethod
    def create_delete_request(
        account_id: int,
        friend_id: str
    ) -> "AccountFriendRequest":
        """
        创建删除好友请求
        
        用于 DeleteFriendPostHook 或其他任务需要删除好友时调用。
        PostHook 场景下应先更新 friendship 表记录，再触发同步删除任务。
        
        Args:
            account_id: 执行删除的账号ID
            friend_id: 要删除的好友 friend_id
            
        Returns:
            创建的请求记录
        """
        # 0. 先更新 friendship 表记录（双向删除）
        FriendshipRepository().remove_friendship(
            account_id=account_id,
            friend_id=friend_id,
        )
        # 1. 创建删除请求记录
        request = FriendRequestRepository().create(
            from_account_id=account_id,
            to_friend_id=None,
            request_type="delete",
            status="deleting"
        )
        
        # 2. 触发 ManageFriendshipTask 调度（应优先执行）
        TaskInstanceRepository().update_status_to_pending(
            account_id=account_id,
            task_type="manage_friendship"
        )
        
        return request
    
    @staticmethod
    def is_friend(account_id: int, friend_id: str) -> bool:
        """
        检查是否是好友
        
        Args:
            account_id: 账号ID
            friend_id: 好友 friend_id
            
        Returns:
            True 如果是好友
        """
        return FriendshipRepository().exists(
            account_id=account_id,
            friend_id=friend_id
        )
```

---

## 五、管理好友关系任务（beads-ug0）

### 5.1 任务定义

```python
# src/ptcgp_auto_v2/tasks/manage_friendship.py

from ptcgp_auto_v2.core.task_base import Task, TaskRegistry, TaskResult, ResetType
from ptcgp_auto_v2.db.repositories import (
    FriendRequestRepository,
    FriendshipRepository,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    input_text,
    navigate_back,
    tap_ok,
    tap_template_or_text,
    tap_text_exact,
)

@TaskRegistry.register("manage_friendship")
class ManageFriendshipTask(Task):
    """
    管理好友关系任务
    
    统一处理发送、接受、删除好友请求。
    扫描 account_friend_request 表，根据记录执行相应操作。
    """
    
    task_type = "manage_friendship"
    reset_type = ResetType.ONCE
    
    # 任务专用页面
    pages = FRIEND_PAGES

    # TODO: 本任务当前仅为框架占位，所有页面识别与交互流程需后续完善
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_request = None
        self._action_cache: dict[str, bool] = {}
        self._last_page_name: str | None = None

    # TODO: 以下方法均为占位框架，具体逻辑需结合真实页面完善

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置操作缓存（进入新页面时调用）"""
        self._action_cache.clear()
    
    def on_start(self):
        """任务开始前的准备"""
        self.requests_to_process = []
        self._action_cache.clear()
        self._last_page_name = None
    
    def is_completed(self) -> bool:
        """检查是否所有请求都处理完成"""
        return len(self.requests_to_process) == 0
    
    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """页面响应逻辑"""
        if page_name != self._last_page_name:
            self._reset_action_cache()
            self._last_page_name = page_name

        handlers = {
            "main_menu": self._open_friends,
            "friend_list": self._check_next_request,
            "friend_search": self._search_friend,
            "friend_request_confirm": self._confirm_send,
            "friend_request_sent": self._mark_sended,
            "friend_requests": self._accept_requests,
            "friend_request_accept_confirm": self._confirm_accept,
            "friend_profile": self._click_remove,
            "friend_remove_confirm": self._confirm_remove,
        }
        
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        
        return ActionResult.wait(1.0)
    
    def _check_next_request(self, page_info) -> ActionResult:
        """检查并处理下一个请求"""
        # 获取当前账号的所有待处理请求
        if not self.requests_to_process:
            self.requests_to_process = self._get_pending_requests()
        
        if not self.requests_to_process:
            return ActionResult.ok()  # 全部处理完成
        
        self.current_request = self.requests_to_process[0]
        
        # 根据请求类型和状态执行不同操作
        if self.current_request.request_type == "add":
            return self._handle_add_request()
        elif self.current_request.request_type == "delete":
            return self._handle_delete_request()
        
        return ActionResult.wait(1.0)
    
    def _get_pending_requests(self) -> List["AccountFriendRequest"]:
        """获取当前账号的所有待处理请求"""
        repo = FriendRequestRepository()
        
        # 1. 我是发送方的 sending 请求
        sending = repo.get_by_from_account_and_status(
            from_account_id=self.account.id,
            status="sending"
        )
        
        # 2. 我是接收方的 sended 请求（需要接受）
        sended = repo.get_by_to_account_and_status(
            to_account_id=self.account.id,
            status="sended"
        )
        
        # 3. 删除请求（我是执行方）
        deleting = repo.get_by_from_account_and_type(
            from_account_id=self.account.id,
            request_type="delete",
            status="deleting"
        )
        
        return sending + sended + deleting
    
    def _handle_add_request(self) -> ActionResult:
        """处理添加好友请求"""
        req = self.current_request
        
        if req.status == "sending":
            # 我需要发送请求
            return self._start_send_request()
        
        elif req.status == "sended":
            # 我是接收方，需要接受
            return self._start_accept_request()
        
        return ActionResult.wait(1.0)
    
    def _start_send_request(self) -> ActionResult:
        """开始发送好友请求流程"""
        if self._is_action_done("add_clicked"):
            return ActionResult.wait(1.0)

        ocr_results = self.page_detector.get_last_page_context()[1]
        add_patterns = get_text_patterns("friend_add")
        result = tap_template_or_text(
            self.adb,
            self.page_detector,
            ocr_results,
            None,
            add_patterns,
            wait=1.0,
        )
        if result:
            self._mark_action_done("add_clicked")
            return result
        return ActionResult.wait(1.0)
    
    def _search_friend(self, page_info) -> ActionResult:
        """搜索好友"""
        friend_id = self.current_request.to_friend_id

        if self._is_action_done("friend_searched"):
            return ActionResult.wait(1.0)

        # 输入 friend_id
        input_text(self.adb, friend_id, wait=0.5)
        ocr_results = page_info.get("ocr_results", [])
        search_patterns = get_text_patterns("friend_search")
        result = tap_template_or_text(
            self.adb,
            self.page_detector,
            ocr_results,
            None,
            search_patterns,
            wait=1.5,
        )
        if result:
            self._mark_action_done("friend_searched")
            return result
        return ActionResult.wait(1.0)
    
    def _confirm_send(self, page_info) -> ActionResult:
        """确认发送请求"""
        ocr_results = page_info.get("ocr_results", [])
        confirm_patterns = get_text_patterns("send_friend_request_confirm")
        result = tap_text_exact(self.adb, ocr_results, confirm_patterns, wait=1.0)
        return result or ActionResult.wait(1.0)
    
    def _mark_sended(self, page_info) -> ActionResult:
        """标记为已发送"""
        req = self.current_request
        
        # 判断是系统内账号还是外部账号
        if req.to_account_id:
            # 系统内账号：更新为 sended，等待对方接受
            req.status = "sended"
            FriendRequestRepository().update(req)
            
            # 触发对方账号的 ManageFriendshipTask
            TaskInstanceRepository().update_status_to_pending(
                account_id=req.to_account_id,
                task_type="manage_friendship"
            )
        else:
            # 外部账号：直接标记为 completed
            req.status = "completed"
            FriendRequestRepository().update(req)
            
            # 在 friendship 表创建记录（单向）
            FriendshipRepository().create(
                account_id=req.from_account_id,
                friend_id=req.to_friend_id,
                friend_account_id=None
            )
        
        # 从处理列表移除
        self.requests_to_process.pop(0)
        self.current_request = None
        
        return ActionResult.wait(1.0)
    
    def _start_accept_request(self) -> ActionResult:
        """开始接受好友请求流程"""
        if self._is_action_done("request_list_opened"):
            return ActionResult.wait(1.0)

        ocr_results = self.page_detector.get_last_page_context()[1]
        request_patterns = get_text_patterns("friend_requests")
        result = tap_template_or_text(
            self.adb,
            self.page_detector,
            ocr_results,
            None,
            request_patterns,
            wait=1.0,
        )
        if result:
            self._mark_action_done("request_list_opened")
            return result
        return ActionResult.wait(1.0)
    
    def _accept_requests(self, page_info) -> ActionResult:
        """处理交友申请列表"""
        req = self.current_request
        
        # OCR 识别列表中的 friend_id
        # 找到匹配 req.from_account_id 的 friend_id 的请求
        from_friend_id = req.from_account.friend_id
        
        if self._find_and_accept_request(from_friend_id, page_info):
            return ActionResult.wait(1.0)
        
        # 未找到，可能已完成
        self.requests_to_process.pop(0)
        self.current_request = None
        return ActionResult.wait(1.0)
    
    def _confirm_accept(self, page_info) -> ActionResult:
        """确认接受请求"""
        ocr_results = page_info.get("ocr_results", [])
        accept_patterns = get_text_patterns("accept")
        result = tap_text_exact(self.adb, ocr_results, accept_patterns, wait=1.0)
        if not result:
            return ActionResult.wait(1.0)
        
        req = self.current_request
        
        # 更新请求状态
        req.status = "completed"
        FriendRequestRepository().update(req)
        
        # 在 friendship 表创建双向记录
        FriendshipRepository().create(
            account_id=req.to_account_id,
            friend_id=req.from_account.friend_id,
            friend_account_id=req.from_account_id
        )
        FriendshipRepository().create(
            account_id=req.from_account_id,
            friend_id=req.to_account.friend_id,
            friend_account_id=req.to_account_id
        )
        
        # 从处理列表移除
        self.requests_to_process.pop(0)
        self.current_request = None
        
        return ActionResult.wait(1.0)
    
    def _handle_delete_request(self) -> ActionResult:
        """处理删除好友请求"""
        # 首版仅支持同步删除：删除不在 friendship 表中的所有好友
        return self._sync_friend_list()
    
    def _sync_friend_list(self) -> ActionResult:
        """同步好友列表（删除不在表中的好友）"""
        # TODO: 补充好友列表滚动策略、翻页终止条件
        # TODO: 明确 friend_id OCR 提取规则与模板匹配
        # 获取当前好友列表中的所有 friend_id
        friend_ids_in_game = self._get_friend_ids_from_game()
        
        # 获取数据库中应该存在的好友 friend_id
        friend_ids_in_db = FriendshipRepository().get_friend_ids(
            account_id=self.account.id
        )
        
        # 找出需要删除的
        to_delete = set(friend_ids_in_game) - set(friend_ids_in_db)
        
        if not to_delete:
            # 没有需要删除的，标记请求完成
            self.current_request.status = "completed"
            FriendRequestRepository().update(self.current_request)
            self.requests_to_process.pop(0)
            self.current_request = None
            return ActionResult.wait(1.0)
        
        # 删除第一个好友
        friend_id = list(to_delete)[0]
        return self._delete_specific_friend(friend_id)
    
    def _delete_specific_friend(self, friend_id: str) -> ActionResult:
        """同步删除流程内部删除单个好友"""
        # TODO: 删除流程仅为框架示意，后续需结合真实页面调试
        # 在好友列表中找到该好友并点击
        if self._find_and_click_friend(friend_id):
            return ActionResult.wait(1.0)
        
        # 未找到，可能需要滚动
        if not self._scroll_friend_list():
            # 滚动后仍找不到，可能已删除
            return ActionResult.wait(1.0)
        
        return ActionResult.wait(1.0)
    
    def _click_remove(self, page_info) -> ActionResult:
        """点击移除好友按钮"""
        # TODO: 仅为框架示意，后续需完善页面定位与点击策略
        ocr_results = page_info.get("ocr_results", [])
        friend_patterns = get_text_patterns("friend")
        result = tap_text_exact(self.adb, ocr_results, friend_patterns, wait=1.0)
        return result or ActionResult.wait(1.0)
    
    def _confirm_remove(self, page_info) -> ActionResult:
        """确认移除"""
        # TODO: 仅为框架示意，后续需完善页面定位与点击策略
        ocr_results = page_info.get("ocr_results", [])
        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            # 删除完成后返回好友列表页
            back_patterns = get_text_patterns("back_button")
            return navigate_back(
                self.adb, self.page_detector, ocr_results, back_patterns
            )
        return ActionResult.wait(1.0)
```

---

## 六、具体 Hook 实现（beads-ug0 的一部分）

### 6.1 FriendPreHook（前置检查）

```python
# src/ptcgp_auto_v2/hooks/friend_hooks.py

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult
from ptcgp_auto_v2.services.friendship_service import FriendshipService

class FriendPreHook(Hook):
    """
    好友关系前置检查 Hook
    
    在需要好友关系的任务前检查是否已是指定账号的好友。
    如果不是，创建添加好友请求并触发 ManageFriendshipTask。
    """
    
    def __init__(self, target_friend_id: str, target_account_id: Optional[int] = None):
        """
        Args:
            target_friend_id: 目标好友的 friend_id
            target_account_id: 目标好友的账号ID（如果是系统内账号）
        """
        self.target_friend_id = target_friend_id
        self.target_account_id = target_account_id
    
    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """
        执行前置检查
        
        Returns:
            (HookResult.CONTINUE, {}): 已是好友，继续执行主任务
            (HookResult.INSERT_TASK, data): 需要插入 manage_friendship 任务，暂停主任务
        """
        # 检查是否已是好友
        is_friend = FriendshipService.is_friend(
            account_id=context.account.id,
            friend_id=self.target_friend_id
        )
        
        if is_friend:
            return HookResult.CONTINUE, {}
        
        # 检查是否已有 pending 的请求
        existing = FriendRequestRepository().get_pending_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id
        )
        
        if existing:
            # 已有请求，让执行器插入 manage_friendship 任务
            # FriendshipService.create_add_request() 已自动触发，但这里确保执行
            return HookResult.INSERT_TASK, {
                "task_type": "manage_friendship",
                "priority": "high",
                "reason": "已有好友请求待处理"
            }
        
        # 创建新的好友请求（FriendshipService 会自动触发 manage_friendship）
        FriendshipService.create_add_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id,
            to_account_id=self.target_account_id
        )
        
        # 返回需要执行前置任务
        return HookResult.INSERT_TASK, {
            "task_type": "manage_friendship",
            "priority": "high",
            "reason": "需要建立好友关系"
        }
```

### 6.2 DeleteFriendPostHook（后置删除）

```python
# src/ptcgp_auto_v2/hooks/friend_hooks.py

class DeleteFriendPostHook(Hook):
    """
    删除好友后置 Hook
    
    在任务完成后删除好友。
    用于送卡任务完成后清理好友关系。
    """
    
    def __init__(self, target_friend_id: str):
        """
        Args:
            target_friend_id: 要删除的好友 friend_id
        """
        self.target_friend_id = target_friend_id
    
    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """
        执行后置删除
        
        通过 FriendshipService 更新好友关系表并创建删除请求，
        同时触发 ManageFriendshipTask（优先执行）。
        PostHook 不需要暂停主任务，所以返回 CONTINUE。
        """
        # 更新好友关系并创建删除请求（FriendshipService 会自动触发 manage_friendship）
        FriendshipService.create_delete_request(
            account_id=context.account.id,
            friend_id=self.target_friend_id
        )
        
        # PostHook 不需要等待，异步执行即可
        return HookResult.CONTINUE, {}
```

**后置任务优先级补充：** PostHook 触发 `manage_friendship` 后，
执行器应将该任务插入当前账号批次队列的前部或标记高优先级，
确保“后置任务优先执行”的需求落地。

**具体落地建议：**
1. `update_status_to_pending` 时写入高优先级字段（若已有 priority）。
2. 执行器收到 `post_hook` 触发后，将任务插入 `pending_tasks` 队首。
3. 若当前任务仍在执行，待其完成后优先调度该任务。

### 6.3 使用示例（送卡任务）

```python
# src/ptcgp_auto_v2/tasks/send_card.py

from ptcgp_auto_v2.hooks.friend_hooks import FriendPreHook, DeleteFriendPostHook

@TaskRegistry.register("send_card")
class SendCardTask(Task):
    task_type = "send_card"
    reset_type = ResetType.ONCE
    
    def __init__(self, target_friend_id: str, card_id: str, **kwargs):
        super().__init__(**kwargs)
        
        # 配置前置检查：确保是好友
        self.pre_hooks = [
            FriendPreHook(target_friend_id=target_friend_id)
        ]
        
        # 配置后置删除：送卡完成后删除好友
        self.post_hooks = [
            DeleteFriendPostHook(target_friend_id=target_friend_id)
        ]
        
        self.target_friend_id = target_friend_id
        self.card_id = card_id
```

---

## 七、Repository 层接口

### 7.1 FriendRequestRepository

```python
# src/ptcgp_auto_v2/db/repositories/friend_request_repository.py

from typing import List, Optional
from sqlmodel import Session, select
from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountFriendRequest

class FriendRequestRepository:
    """好友请求数据访问"""
    
    def create(
        self,
        from_account_id: int,
        to_friend_id: Optional[str],
        to_account_id: Optional[int] = None,
        request_type: str = "add",
        status: str = "sending"
    ) -> AccountFriendRequest:
        """创建请求记录"""
        with Session(get_engine()) as session:
            request = AccountFriendRequest(
                from_account_id=from_account_id,
                to_friend_id=to_friend_id,
                to_account_id=to_account_id,
                request_type=request_type,
                status=status
            )
            session.add(request)
            session.commit()
            session.refresh(request)
            return request
    
    def get_by_from_account_and_status(
        self,
        from_account_id: int,
        status: str
    ) -> List[AccountFriendRequest]:
        """获取发送方的指定状态请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.status == status
            )
            return session.exec(statement).all()
    
    def get_by_to_account_and_status(
        self,
        to_account_id: int,
        status: str
    ) -> List[AccountFriendRequest]:
        """获取接收方的指定状态请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.to_account_id == to_account_id,
                AccountFriendRequest.status == status
            )
            return session.exec(statement).all()
    
    def get_by_from_account_and_type(
        self,
        from_account_id: int,
        request_type: str,
        status: str
    ) -> List[AccountFriendRequest]:
        """获取发送方的指定类型和状态的请求"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.request_type == request_type,
                AccountFriendRequest.status == status
            )
            return session.exec(statement).all()
    
    def get_pending_request(
        self,
        from_account_id: int,
        to_friend_id: str
    ) -> Optional[AccountFriendRequest]:
        """获取待处理的请求（应用层防止重复）"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendRequest).where(
                AccountFriendRequest.from_account_id == from_account_id,
                AccountFriendRequest.to_friend_id == to_friend_id,
                AccountFriendRequest.status.in_(["sending", "sended"])
            )
            return session.exec(statement).first()
    
    def update(self, request: AccountFriendRequest):
        """更新请求记录"""
        with Session(get_engine()) as session:
            session.add(request)
            session.commit()
            session.refresh(request)
            return request
```

### 7.2 FriendshipRepository

```python
# src/ptcgp_auto_v2/db/repositories/friendship_repository.py

from typing import List
from sqlmodel import Session, select
from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountFriendship

class FriendshipRepository:
    """好友关系数据访问"""
    
    def create(
        self,
        account_id: int,
        friend_id: str,
        friend_account_id: Optional[int] = None
    ) -> AccountFriendship:
        """创建好友关系（幂等，如果已存在则返回现有记录）"""
        with Session(get_engine()) as session:
            # 检查是否已存在
            existing = self._get_by_account_and_friend(
                session, account_id, friend_id
            )
            if existing:
                return existing
            
            friendship = AccountFriendship(
                account_id=account_id,
                friend_id=friend_id,
                friend_account_id=friend_account_id
            )
            session.add(friendship)
            session.commit()
            session.refresh(friendship)
            return friendship
    
    def _get_by_account_and_friend(
        self,
        session: Session,
        account_id: int,
        friend_id: str
    ) -> Optional[AccountFriendship]:
        """内部方法：根据账号和好友ID查询"""
        statement = select(AccountFriendship).where(
            AccountFriendship.account_id == account_id,
            AccountFriendship.friend_id == friend_id
        )
        return session.exec(statement).first()
    
    def exists(self, account_id: int, friend_id: str) -> bool:
        """检查好友关系是否存在"""
        with Session(get_engine()) as session:
            return self._get_by_account_and_friend(
                session, account_id, friend_id
            ) is not None
    
    def get_friend_ids(self, account_id: int) -> List[str]:
        """获取账号的所有好友 friend_id 列表"""
        with Session(get_engine()) as session:
            statement = select(AccountFriendship.friend_id).where(
                AccountFriendship.account_id == account_id
            )
            return [row[0] for row in session.exec(statement).all()]
    
    def delete(self, account_id: int, friend_id: str):
        """删除好友关系（物理删除）"""
        with Session(get_engine()) as session:
            friendship = self._get_by_account_and_friend(
                session, account_id, friend_id
            )
            if friendship:
                session.delete(friendship)
                session.commit()

    def remove_friendship(self, account_id: int, friend_id: str):
        """删除双向好友关系（A→B 与 B→A）"""
        with Session(get_engine()) as session:
            forward = self._get_by_account_and_friend(
                session, account_id, friend_id
            )
            if forward:
                session.delete(forward)

                if forward.friend_account_id:
                    statement = select(AccountFriendship).where(
                        AccountFriendship.account_id == forward.friend_account_id,
                        AccountFriendship.friend_account_id == account_id,
                    )
                    reverse = session.exec(statement).first()
                    if reverse:
                        session.delete(reverse)

            session.commit()
```

### 7.3 TaskInstanceRepository 扩展

```python
# src/ptcgp_auto_v2/db/repositories/task_instance_repository.py (扩展)

class TaskInstanceRepository:
    # ... 现有方法 ...
    
    def update_status_to_pending(self, account_id: int, task_type: str):
        """
        将指定任务的 TaskInstance 状态更新为 pending
        
        用于 Hook 触发任务调度。
        """
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                TaskInstance.account_id == account_id,
                TaskInstance.task_type == task_type
            )
            instance = session.exec(statement).first()
            
            if instance:
                instance.status = TaskStatus.PENDING.value
                instance.updated_at = datetime.now()
                session.add(instance)
                session.commit()
```

---

## 八、页面识别配置

页面规则在 Task 文件内部通过 `_build_manage_friendship_pages()` 函数定义，与 Task 类在一起。

**TODO:** 页面规则与 locale key 需结合真实页面补齐，当前仅为框架占位。

```python
# src/ptcgp_auto_v2/tasks/manage_friendship.py

def _build_manage_friendship_pages() -> list[dict]:
    """构建好友管理任务页面规则"""
    from ptcgp_auto_v2.locales import get_text_patterns
    
    return [
        {
            "name": "friend_list",
            "templates": ["friend_list_header"],
            "texts": get_text_patterns("friend_list"),
        },
        {
            "name": "friend_search",
            "templates": ["friend_search_input"],
            "texts": get_text_patterns("friend_search"),
        },
        {
            "name": "friend_request_confirm",
            "templates": ["send_request_button"],
            "texts": get_text_patterns("send_friend_request"),
        },
        {
            "name": "friend_request_sent",
            "templates": ["request_sent_success"],
            "texts": get_text_patterns("request_sent"),
        },
        {
            "name": "friend_requests",
            "templates": ["friend_requests_header"],
            "texts": get_text_patterns("friend_requests"),
        },
        {
            "name": "friend_request_accept_confirm",
            "templates": ["accept_request_button"],
            "texts": get_text_patterns("accept"),
        },
        {
            "name": "friend_profile",
            "templates": ["friend_profile_card"],
            "texts": get_text_patterns("friend"),
        },
        {
            "name": "friend_remove_confirm",
            "templates": ["confirm_dialog"],
            "texts": get_text_patterns("remove_friend_confirm"),
        },
    ]


@TaskRegistry.register("manage_friendship")
class ManageFriendshipTask(Task):
    """管理好友关系任务"""
    
    task_type = "manage_friendship"
    reset_type = ResetType.ONCE
    
    # 页面规则与 Task 定义在一起
    pages = _build_manage_friendship_pages()
    max_unknown_pages = 20
    
    # ... 其他实现
```

**注意：**
- 页面文本必须通过 `get_text_patterns()` 获取，支持多语言
- 所有硬编码文本必须在 locale 中定义，以 zh_Hant 为基准
- 页面规则与 Task 类定义在同一个文件中

---

## 九、实施检查清单

### Phase 1: 数据库模型 (beads-cli)
- [x] 创建 `account_friend_request.py` 模型
- [x] 创建 `account_friendship.py` 模型
- [x] 更新 `models/__init__.py` 导出新模型
- [x] 创建 `FriendRequestRepository`
- [x] 创建 `FriendshipRepository`
- [x] 扩展 `TaskInstanceRepository.update_status_to_pending()`

### Phase 2: Hook 机制 (beads-x4a)
- [x] 创建 `core/hooks.py`（Hook 基类、HookContext、HookResult）
- [x] 修改 `core/task_base.py` 支持 pre/post hooks
- [x] 修改 `core/executor.py` 支持 HookContext 注入
- [ ] 编写单元测试

### Phase 3: 业务实现 (beads-ug0)
- [x] 创建 `services/friendship_service.py`（开放接口）
- [x] 创建 `hooks/friend_hooks.py`（FriendPreHook、DeleteFriendPostHook）
- [x] 创建 `tasks/manage_friendship.py`（ManageFriendshipTask，包含页面规则定义）
- [x] 在 locale 中添加好友相关文本配置
- [ ] 模拟器实测

---

## 十、测试计划

> ⚠️ **备注：测试计划暂时跳过**
> 
> 待全部代码完成后，经审阅确认后再编写测试代码。

<!--
### 10.1 单元测试
- [ ] Repository 层 CRUD 测试
- [ ] FriendshipService 接口测试
- [ ] Hook 逻辑测试（使用 Mock Context）

### 10.2 集成测试
- [ ] 系统内账号 A→B 完整流程（发送 → 接受 → friendship 表验证）
- [ ] 外部账号 A→X 流程（发送后直接完成）
- [ ] 删除好友流程（仅同步删除）
- [ ] Hook 触发 TaskInstance 调度测试

### 10.3 模拟器测试
- [ ] 单账号好友操作
- [ ] 多账号好友互动
- [ ] 异常情况处理（网络断开、游戏崩溃）
-->


---

## 附录

### beads 任务最终结构

```
📦 Feature: 处理好友关系功能 (beads-dq3) [P1]
   ├── 🟢 beads-cli: 数据库模型设计 [P0] - 可执行
   ├── 🟡 beads-x4a: Hook 机制实现 [P1] - 依赖 beads-cli
   └── 🟡 beads-ug0: 管理好友关系任务 [P2] - 依赖 beads-cli, beads-x4a

已删除: beads-epe, beads-88n, beads-skd
```

### 参考文档
- **需求文档**: `docs/needs/08-处理好友关系.md`
- **相关代码**:
  - `src/ptcgp_auto_v2/core/task_base.py` - 任务基类
  - `src/ptcgp_auto_v2/core/executor.py` - 执行器
  - `src/ptcgp_auto_v2/db/models/` - 数据库模型目录

---

## 十一、对话补充：页面实测流程原文归档（2026-02-10）

> 本节保存开发者在对话中的关键流程描述原文，后续实现必须以此为准，禁止擅自泛化。

### 11.1 入口与主页面

- 首先进入游戏，匹配底部模板 `icon_community` 并点击。
- 进入社群后，通过 OCR 点击「朋友」，这里要求精确点击。
- 朋友页面有三个 tab：
  - 左下「朋友」：当前好友列表
  - 中间「申請中」：自己发出的好友申请（可取消）
  - 右侧「需回覆」：收到的好友申请

### 11.2 好友详情与返回

- 点击朋友条目进入账号详情页（含朋友ID、昵称、等级等）。
- 返回时点击 `btn_close`（X）回到列表页。

### 11.3 添加好友流程（发送）

1. 在朋友列表页点击模板 `icon_add_friends`。
2. 出现底部弹层，匹配模板 `icon_search` 后，不点模板本体，先点击输入区域。
3. 输入 friend_id（可参考 init_account/fetch_account_info 中输入文本处理方式）。
4. 点击 `icon_search` 搜索。
5. 搜索结果页判定：
   - 若出现「取消交友邀請」表示已申请中（pending）。
   - 若匹配 `icon_green_yes --scale 0.8`，表示已是好友。
6. 结束后通过 `btn_close` 返回，必要时连续关闭两次回到好友列表。

### 11.4 需回覆流程（接受/拒绝）

- 在「需回覆」页可稳定匹配：
  - `icon_green_yes`（接受）
  - `icon_red_no`（拒绝）
- 必须先点对应条目的 `Lv` 进入详情页，读取 friend_id 后再决策。
- 每次处理一条后，该条消失，其余条目上移；通常始终处理第一条即可。
- 没有下一页概念：页面不存在绿勾/红叉时即视为处理完成。

### 11.5 删除好友流程

- 列表页无法直接拿到 friend_id，需要依赖昵称定位候选并进入详情确认 friend_id。
- 若确认需要删除，返回列表后点击绿色勾，出现「要移除朋友嗎？」弹窗，点击 OK 完成。

---

## 十二、对话补充：需求纠正与强约束

### 12.1 用户纠正（原话）

> “我上面的文字都是精确的，你不要画蛇添足，多补充其他类似的字样。”

> “只要我说过用模板匹配的，那说明就不要使用文字，不要做兜底。”

> “所有我给你的模板，都是足够稳定的，如果提供了scale，也是完全可靠的，你不要随便去除或者更改。”

> “需回复页面必须进入详情页去判断是否我们需要接受的id，如果不是，直接取消。每次接收时，需要获取当前所有待接受的friendid，如果不在列表里的其他friendid，我们默认不接受。”

### 12.2 强制实现规则

1. 文案按用户提供精确值匹配，不扩展同义词。
2. 指定模板场景仅使用模板，不加文字兜底。
3. 指定 `scale` 的模板匹配必须固定使用该 scale。
4. `需回覆` 必须“先详情取 friend_id，再决定 accept/reject”。
5. 每轮接收前获取待接受白名单 friend_id；不在白名单默认拒绝。
6. `需回覆` 无绿勾/红叉即结束，不实现翻页/滚动逻辑。
7. 默认处理第一条，处理后继续下一轮直到结束。

---

## 十三、Web 管理页探索与设计补充

### 13.1 目标

新增 Friendship 管理入口，支持直接创建好友请求，减少手工改库成本，方便后续调试与运营。

### 13.2 现状探索结论

- 当前 Management 侧边栏仅有 Accounts / Plans / Tasks / Metadata。
- 目前没有 Friendship 页面与创建请求入口。

### 13.3 推荐实现落点

- Router：`src/ptcgp_auto_v2/web/routers/friendship.py`
- Service：`src/ptcgp_auto_v2/web/services/friendship_admin_service.py`
- Template：`src/ptcgp_auto_v2/web/templates/partials/friendship_list.html`
- i18n：`src/ptcgp_auto_v2/web/locales/zh_CN.json`、`src/ptcgp_auto_v2/web/locales/en.json`
- App 挂载：`src/ptcgp_auto_v2/web/app.py`
- 侧边栏 hash 与自动选择：
  - `src/ptcgp_auto_v2/web/templates/index.html`
  - `src/ptcgp_auto_v2/web/static/js/modules/tabs.js`
  - `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`

### 13.4 一期交互设计（最小闭环）

1. 侧边栏新增 Friendship 菜单。
2. 页面提供“创建 add 请求”表单：
   - 发送方账号（from_account_id）
   - 目标类型（系统内账号 / 外部 friend_id）
   - 目标账号（to_account_id）或外部 friend_id（to_friend_id）
3. 提交后调用 `FriendshipService.create_add_request(...)`。
4. 同页展示请求队列表格（id/from/to/status/failed_reason/updated_at），支持 HTMX 刷新。

### 13.5 关键校验

- from_account 必填
- 系统内目标账号需存在且有 friend_id
- 外部 friend_id 格式合法（允许连字符输入，入库归一化）
- 禁止自己加自己
- 已有 pending 请求时阻止重复创建

---

## 十四、下一步执行建议

### Step 1（先做 Web 闭环）

1. 新增 friendship Router/Service/Template 并挂载。
2. 增加侧边栏入口与 i18n 文案。
3. 完成“系统内账号 + 外部 friend_id”创建请求。
4. 完成请求列表展示与刷新。

### Step 2（联动任务验证）

1. 通过 Web 创建一条系统内 add 请求、一条外部 add 请求。
2. 运行：`PYTHONPATH=.:src python main_v2.py --task manage_friendship --account <id>`
3. 重点验证需回覆详情判定与白名单拒绝策略。

### Step 3（测试与回归）

1. 补 web router/service 测试（参数校验、创建成功/失败、重复请求拦截）。
2. 回归任务测试：
   - `PYTHONPATH=.:src pytest -q src/ptcgp_auto_v2/tests/tasks/test_manage_friendship_task.py`
3. 回填本计划完成状态与实机日志结论。

---

*本计划已根据 2026-02-10 对话补充更新，后续实现以本文件为准。*
