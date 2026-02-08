# 好友关系功能实施计划

> **原始需求**: docs/needs/08-处理好友关系.md  
> **创建日期**: 2026-02-08  
> **关联 beads Feature**: beads-dq3 "处理好友关系功能"  
> **作者**: AI Assistant  
> **状态**: 待实施

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
| 删除策略 | **与好友关系表同步** | 删除不在 friendship 表中的好友 |
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
    - delete 类型: deleting -> deleted/failed
    """
    
    __tablename__ = "account_friend_requests"
    
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
    # delete 类型: deleting -> deleted / failed
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

**delete 类型请求:**
```
deleting ──删除成功──► deleted
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
    INSERT_TASK = "insert"     # 已插入前置任务，暂停当前任务


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
    def run(self, context: HookContext) -> HookResult:
        """
        执行 Hook 逻辑
        
        Args:
            context: 执行上下文
            
        Returns:
            HookResult 指示后续操作
        """
        pass
    
    def trigger_task(self, context: HookContext, task_type: str):
        """
        触发指定任务的调度
        
        将指定任务的 TaskInstance 状态更新为 pending，
        让调度器在下次循环时自动调度。
        
        Args:
            context: 执行上下文
            task_type: 任务类型
        """
        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
        
        TaskInstanceRepository().update_status_to_pending(
            account_id=context.account.id,
            task_type=task_type
        )
```

### 3.2 Task 基类集成

```python
# src/ptcgp_auto_v2/core/task_base.py (修改)

class Task(ABC):
    """任务基类"""
    
    # 新增属性
    pre_hooks: List["Hook"] = []
    post_hooks: List["Hook"] = []
    
    def execute(self) -> TaskResult:
        """执行任务主循环"""
        from ptcgp_auto_v2.core.hooks import HookResult
        
        self.on_start()
        
        # 执行 pre_hooks
        for hook in self.pre_hooks:
            result = hook.run(self._hook_context)
            
            if result == HookResult.ABORT:
                result = TaskResult.fail("PreHook aborted")
                self.on_complete(result)
                return result
            
            if result == HookResult.INSERT_TASK:
                # 前置任务已插入，当前任务暂停
                result = TaskResult.skip("Waiting for pre-task completion")
                self.on_complete(result)
                return result
        
        # 执行主任务逻辑
        result = self._execute_main_loop()
        
        # 执行 post_hooks（无论主任务成功失败）
        for hook in self.post_hooks:
            hook.run(self._hook_context)
        
        self.on_complete(result)
        return result
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
        friend_id: Optional[str] = None
    ) -> "AccountFriendRequest":
        """
        创建删除好友请求
        
        用于 DeleteFriendPostHook 或其他任务需要删除好友时调用。
        
        Args:
            account_id: 执行删除的账号ID
            friend_id: 要删除的好友 friend_id（为 None 表示全量同步）
            
        Returns:
            创建的请求记录
        """
        # 1. 创建删除请求记录
        request = FriendRequestRepository().create(
            from_account_id=account_id,
            to_friend_id=friend_id,  # 可能为 None
            request_type="delete",
            status="deleting"
        )
        
        # 2. 触发 ManageFriendshipTask 调度
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
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_request = None
    
    def on_start(self):
        """任务开始前的准备"""
        self.requests_to_process = []
    
    def is_completed(self) -> bool:
        """检查是否所有请求都处理完成"""
        return len(self.requests_to_process) == 0
    
    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """页面响应逻辑"""
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
        # 点击添加好友按钮
        self.adb.click(800, 400)  # 根据实际位置调整
        return ActionResult.wait(1.0)
    
    def _search_friend(self, page_info) -> ActionResult:
        """搜索好友"""
        friend_id = self.current_request.to_friend_id
        
        # 输入 friend_id
        self.adb.input_text(friend_id)
        self.adb.click(900, 1200)  # 搜索按钮
        return ActionResult.wait(2.0)
    
    def _confirm_send(self, page_info) -> ActionResult:
        """确认发送请求"""
        self.adb.click(800, 1400)  # 确认按钮
        return ActionResult.wait(1.0)
    
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
        # 点击交友申请按钮
        self.adb.click(600, 300)  # 根据实际位置调整
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
        self.adb.click(800, 1400)  # 确认按钮
        
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
        req = self.current_request
        
        if req.to_friend_id:
            # 删除指定好友
            return self._delete_specific_friend(req.to_friend_id)
        else:
            # 全量同步：删除不在 friendship 表中的所有好友
            return self._sync_friend_list()
    
    def _sync_friend_list(self) -> ActionResult:
        """同步好友列表（删除不在表中的好友）"""
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
            self.current_request.status = "deleted"
            FriendRequestRepository().update(self.current_request)
            self.requests_to_process.pop(0)
            self.current_request = None
            return ActionResult.wait(1.0)
        
        # 删除第一个好友
        friend_id = list(to_delete)[0]
        return self._delete_specific_friend(friend_id)
    
    def _delete_specific_friend(self, friend_id: str) -> ActionResult:
        """删除指定好友"""
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
        # 点击"朋友"文字
        self.adb.click(540, 1600)  # 根据实际位置调整
        return ActionResult.wait(1.0)
    
    def _confirm_remove(self, page_info) -> ActionResult:
        """确认移除"""
        self.adb.click(700, 1100)  # OK按钮
        
        # 检查是否还有更多需要删除的
        if self.current_request.to_friend_id is None:
            # 全量同步模式，继续处理
            return ActionResult.wait(1.0)
        else:
            # 删除特定好友完成
            self.current_request.status = "deleted"
            FriendRequestRepository().update(self.current_request)
            self.requests_to_process.pop(0)
            self.current_request = None
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
    
    def run(self, context: HookContext) -> HookResult:
        """
        执行前置检查
        
        Returns:
            CONTINUE: 已是好友，继续执行主任务
            INSERT_TASK: 已创建好友请求，暂停主任务等待完成
        """
        # 检查是否已是好友
        is_friend = FriendshipService.is_friend(
            account_id=context.account.id,
            friend_id=self.target_friend_id
        )
        
        if is_friend:
            return HookResult.CONTINUE
        
        # 检查是否已有 pending 的请求
        existing = FriendRequestRepository().get_pending_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id
        )
        
        if existing:
            # 已有请求，触发 ManageFriendshipTask 执行
            self.trigger_task(context, "manage_friendship")
            return HookResult.INSERT_TASK
        
        # 创建新的好友请求
        FriendshipService.create_add_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id,
            to_account_id=self.target_account_id
        )
        
        return HookResult.INSERT_TASK
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
    
    def __init__(self, target_friend_id: Optional[str] = None):
        """
        Args:
            target_friend_id: 要删除的好友 friend_id
                               为 None 表示全量同步（删除不在 friendship 表中的）
        """
        self.target_friend_id = target_friend_id
    
    def run(self, context: HookContext) -> HookResult:
        """
        执行后置删除
        
        创建删除请求并触发 ManageFriendshipTask。
        """
        # 创建删除请求
        FriendshipService.create_delete_request(
            account_id=context.account.id,
            friend_id=self.target_friend_id
        )
        
        # 注意：这里不需要等待删除完成，异步执行即可
        return HookResult.CONTINUE
```

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

```python
# src/ptcgp_auto_v2/config/pages/friend_pages.py

FRIEND_PAGES = [
    {
        "name": "friend_list",
        "templates": ["friend_list_header"],
        "texts": ["好友", "朋友"],
    },
    {
        "name": "friend_search",
        "templates": ["friend_search_input"],
        "texts": ["搜索", "请输入ID"],
    },
    {
        "name": "friend_request_confirm",
        "templates": ["send_request_button"],
        "texts": ["发送好友申请"],
    },
    {
        "name": "friend_request_sent",
        "templates": ["request_sent_success"],
        "texts": ["已发送"],
    },
    {
        "name": "friend_requests",
        "templates": ["friend_requests_header"],
        "texts": ["交友申请"],
    },
    {
        "name": "friend_request_accept_confirm",
        "templates": ["accept_request_button"],
        "texts": ["接受"],
    },
    {
        "name": "friend_profile",
        "templates": ["friend_profile_card"],
        "texts": ["朋友"],
    },
    {
        "name": "friend_remove_confirm",
        "templates": ["confirm_dialog"],
        "texts": ["要移除好友吗", "OK"],
    },
]
```

---

## 九、实施检查清单

### Phase 1: 数据库模型 (beads-cli)
- [ ] 创建 `account_friend_request.py` 模型
- [ ] 创建 `account_friendship.py` 模型
- [ ] 更新 `models/__init__.py` 导出新模型
- [ ] 创建 `FriendRequestRepository`
- [ ] 创建 `FriendshipRepository`
- [ ] 扩展 `TaskInstanceRepository.update_status_to_pending()`

### Phase 2: Hook 机制 (beads-x4a)
- [ ] 创建 `core/hooks.py`（Hook 基类、HookContext、HookResult）
- [ ] 修改 `core/task_base.py` 支持 pre/post hooks
- [ ] 修改 `core/executor.py` 支持 HookContext 注入
- [ ] 编写单元测试

### Phase 3: 业务实现 (beads-ug0)
- [ ] 创建 `services/friendship_service.py`（开放接口）
- [ ] 创建 `hooks/friend_hooks.py`（FriendPreHook、DeleteFriendPostHook）
- [ ] 创建 `tasks/manage_friendship.py`（ManageFriendshipTask）
- [ ] 创建 `config/pages/friend_pages.py`
- [ ] 编写集成测试
- [ ] 模拟器实测

---

## 十、测试计划

### 10.1 单元测试
- [ ] Repository 层 CRUD 测试
- [ ] FriendshipService 接口测试
- [ ] Hook 逻辑测试（使用 Mock Context）

### 10.2 集成测试
- [ ] 系统内账号 A→B 完整流程（发送 → 接受 → friendship 表验证）
- [ ] 外部账号 A→X 流程（发送后直接完成）
- [ ] 删除好友流程（指定好友 + 全量同步）
- [ ] Hook 触发 TaskInstance 调度测试

### 10.3 模拟器测试
- [ ] 单账号好友操作
- [ ] 多账号好友互动
- [ ] 异常情况处理（网络断开、游戏崩溃）

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

*计划制定完成，等待实施指令。*
