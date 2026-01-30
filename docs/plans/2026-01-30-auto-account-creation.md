# 定时创建小号机制实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现定时自动创建小号机制，当系统空闲且账号数量未达上限时，自动在可用模拟器上创建新账号

**Architecture:** 
- 创建一个独立的 `AccountCreationScheduler` 组件，在系统空闲时运行
- 复用现有的 `init_account` 任务逻辑和账号同步机制
- 通过检查任务状态（无 pending 任务）和账号数量来决定是否执行创建

**Tech Stack:** Python, SQLModel/SQLAlchemy, ADB, 现有 v2 架构

---

## 前置条件

- 已存在 `init_account` 任务（已完成）
- 已存在账号同步机制 `account_syncer.get_current_account()`
- 已存在设备发现 `device_discovery.discover_devices()`
- 已存在 `reset_game_environment` 和 `restart_app` 方法

---

## Task 1: 创建任务实例仓库查询方法

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`

**Step 1: 添加 has_any_tasks_except_completed 方法**

在 `TaskInstanceRepository` 类中添加新方法，用于检查是否存在非 completed 状态的任务：

```python
def has_any_tasks_except_completed(self) -> bool:
    """检查是否存在非 completed 状态的任务
    
    用于判断系统是否空闲（没有 pending/running/blocked/skipped/failed 任务）
    
    Returns:
        True 表示存在未完成的任务（系统不空闲）
    """
    with Session(get_engine()) as session:
        statement = (
            select(TaskInstance)
            .where(col(TaskInstance.status) != "completed")
            .limit(1)
        )
        return session.exec(statement).first() is not None
```

**Step 2: 添加 count_all_accounts 方法到 AccountRepository**

```python
# 在 src/ptcgp_auto_v2/db/repositories/account_repository.py 中添加

def count_all(self) -> int:
    """统计所有账号数量"""
    with Session(get_engine()) as session:
        statement = select(func.count()).select_from(Account)
        result = session.exec(statement).one()
        return result or 0
```

**Step 3: Commit**

```bash
git add src/ptcgp_auto_v2/db/repositories/
git commit -m "feat: add repository methods for account creation scheduler

- 添加 has_any_tasks_except_completed 检查系统是否空闲
- 添加 count_all 统计账号总数"
```

---

## Task 2: 创建定时账号创建调度器

**Files:**
- Create: `src/ptcgp_auto_v2/core/account_creation_scheduler.py`

**Step 1: 创建调度器类**

```python
# -*- coding: utf-8 -*-
"""
定时创建小号调度器

在系统空闲时自动创建新账号，直到达到指定数量上限。
"""

import logging
import threading
import time
from typing import Optional

from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskInstanceRepository
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import get_current_account, AccountSyncer
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.tasks.init_account import InitAccountTask
from ptcgp_auto_v2.utils.device_discovery import discover_devices
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.card_recognizer import CardRecognizer
from ptcgp_auto_v2.config.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_MAX_ACCOUNTS = 100  # 默认最大账号数量
DEFAULT_CHECK_INTERVAL = 60.0  # 检查间隔（秒）


class AccountCreationScheduler:
    """
    定时账号创建调度器
    
    职责：
    1. 定期检查系统是否空闲（没有 pending/running 等任务）
    2. 检查当前账号数量是否达到上限
    3. 在空闲设备上创建新账号
    """

    def __init__(
        self,
        max_accounts: int = DEFAULT_MAX_ACCOUNTS,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
    ):
        self.max_accounts = max_accounts
        self.check_interval = check_interval
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # 延迟初始化的仓库
        self._account_repo: Optional[AccountRepository] = None
        self._task_instance_repo: Optional[TaskInstanceRepository] = None

    def _init_repositories(self):
        """初始化数据仓库"""
        from ptcgp_auto_v2.db.repositories import (
            AccountRepository,
            TaskInstanceRepository,
        )
        self._account_repo = AccountRepository()
        self._task_instance_repo = TaskInstanceRepository()

    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("账号创建调度器已在运行")
            return

        logger.info(f"启动账号创建调度器 (最大账号数: {self.max_accounts})...")
        self._init_repositories()
        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._main_loop,
            name="AccountCreationScheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("账号创建调度器已启动")

    def stop(self, wait: bool = True):
        """停止调度器"""
        if not self._running:
            return

        logger.info("停止账号创建调度器...")
        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            if wait:
                self._thread.join(timeout=30)

        logger.info("账号创建调度器已停止")

    def _main_loop(self):
        """主循环"""
        while self._running:
            try:
                if self._should_create_account():
                    self._try_create_account()
            except Exception as e:
                logger.exception(f"账号创建调度器异常: {e}")

            # 等待检查间隔或停止信号
            if self._stop_event.wait(timeout=self.check_interval):
                break

    def _should_create_account(self) -> bool:
        """检查是否应该创建新账号"""
        # 1. 检查是否有正在执行的任务（非 completed 状态）
        if self._task_instance_repo.has_any_tasks_except_completed():
            logger.debug("存在未完成的任务，跳过账号创建")
            return False

        # 2. 检查账号数量是否达到上限
        current_count = self._account_repo.count_all()
        if current_count >= self.max_accounts:
            logger.info(f"账号数量 ({current_count}) 已达到上限 ({self.max_accounts})，停止创建")
            return False

        logger.debug(f"系统空闲，当前账号数: {current_count}/{self.max_accounts}")
        return True

    def _try_create_account(self):
        """尝试创建新账号"""
        # 1. 发现可用设备
        device_addresses = discover_devices()
        if not device_addresses:
            logger.debug("没有发现可用设备")
            return

        logger.info(f"发现 {len(device_addresses)} 个设备，尝试创建新账号")

        # 2. 遍历设备尝试创建
        for address in device_addresses:
            if not self._running:
                break

            try:
                if self._create_account_on_device(address):
                    logger.info(f"成功在设备 {address} 创建新账号")
                    return  # 创建成功，退出
            except Exception as e:
                logger.exception(f"在设备 {address} 创建账号失败: {e}")
                continue

        logger.debug("本轮未能在任何设备上创建账号")

    def _create_account_on_device(self, device_address: str) -> bool:
        """
        在指定设备上创建新账号
        
        Args:
            device_address: 设备地址
            
        Returns:
            True 表示创建成功
        """
        # 1. 初始化 ADB 控制器
        adb = AdbController(device_address)
        if not adb.connect():
            logger.warning(f"无法连接到设备 {device_address}")
            return False

        try:
            # 2. 获取当前设备上的账号信息
            syncer = AccountSyncer(adb)
            current_account = syncer.get_current_account()

            switcher = AccountSwitcher(adb)

            if current_account:
                # 账号已在数据库中，说明是已管理的账号
                logger.info(f"设备上存在已管理账号: {current_account.nickname or current_account.game_id}")
                # 直接调用 get_current_account 已经更新了 XML
                # 现在需要重置环境以创建新账号
                switcher.reset_game_environment()
            else:
                # 账号不在数据库中，说明是未管理账号或新设备
                logger.info("设备上存在未管理账号，重置游戏环境")
                switcher.reset_game_environment()

            # 3. 重启游戏，进入新账号创建流程
            logger.info("重启游戏，等待新账号创建...")
            settings = get_settings()
            adb.restart_app(settings.app_package)
            time.sleep(5)  # 等待游戏启动

            # 4. 执行 init_account 任务
            if not self._run_init_account_task(adb):
                logger.error("初始化账号任务失败")
                return False

            # 5. 任务完成后，保存账号信息
            logger.info("获取并保存新账号信息...")
            new_account = syncer.get_current_account()
            if not new_account:
                logger.error("无法获取新创建的账号信息")
                return False

            logger.info(f"成功创建并管理新账号: {new_account.nickname or new_account.game_id}")
            return True

        finally:
            adb.disconnect()

    def _run_init_account_task(self, adb: AdbController) -> bool:
        """
        执行初始化账号任务
        
        Args:
            adb: ADB 控制器
            
        Returns:
            True 表示任务成功完成
        """
        # 初始化 OCR 和页面检测器
        ocr = OcrEngine()
        recognizer = CardRecognizer()
        page_detector = PageDetector(adb, ocr, recognizer)

        # 创建 init_account 任务
        task = InitAccountTask(adb, recognizer, page_detector)
        task.set_stop_event(self._stop_event)

        # 执行任务
        result = task.execute()
        
        if not result.success:
            logger.error(f"初始化任务失败: {result.error}")
            return False

        if result.skipped:
            logger.warning(f"初始化任务被跳过: {result.skip_reason}")
            return False

        return True

    def get_status(self) -> dict:
        """获取调度器状态"""
        current_count = 0
        if self._account_repo:
            current_count = self._account_repo.count_all()

        return {
            "running": self._running,
            "max_accounts": self.max_accounts,
            "current_accounts": current_count,
            "remaining": max(0, self.max_accounts - current_count),
        }
```

**Step 2: Commit**

```bash
git add src/ptcgp_auto_v2/core/account_creation_scheduler.py
git commit -m "feat: add account creation scheduler

- 实现定时检查系统空闲状态
- 在空闲设备上自动创建新账号
- 复用现有 init_account 任务逻辑"
```

---

## Task 3: 集成到主调度器

**Files:**
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`
- Modify: `src/ptcgp_auto_v2/main.py`

**Step 1: 在 Scheduler 中集成 AccountCreationScheduler**

在 `Scheduler` 类的 `__init__` 方法中添加：

```python
# 在 Scheduler.__init__ 中添加
from ptcgp_auto_v2.core.account_creation_scheduler import AccountCreationScheduler

self.account_creation_scheduler: Optional[AccountCreationScheduler] = None
self.enable_auto_account_creation = False  # 默认关闭
self.max_auto_accounts = 100
```

在 `Scheduler.start` 方法中添加启动逻辑：

```python
def start(self):
    """启动调度器"""
    if self._running:
        logger.warning("调度器已在运行")
        return

    logger.info("启动调度器...")
    self._init_repositories()
    self._running = True
    self._executor_pool = ThreadPoolExecutor(
        max_workers=self.config.max_workers,
        thread_name_prefix="TaskExecutor",
    )

    # 启动账号创建调度器（如果启用）
    if self.enable_auto_account_creation:
        self.account_creation_scheduler = AccountCreationScheduler(
            max_accounts=self.max_auto_accounts,
            check_interval=self.config.task_generation_interval,
        )
        self.account_creation_scheduler.start()

    # 在新线程中运行主循环
    self._main_thread = threading.Thread(
        target=self._main_loop,
        name="SchedulerMainLoop",
        daemon=True,
    )
    self._main_thread.start()
    logger.info(
        f"调度器已启动 (设备数: {self.device_pool.total_count}, "
        f"最大并发: {self.config.max_workers})"
    )
```

在 `Scheduler.stop` 方法中添加停止逻辑：

```python
def stop(self, wait: bool = True):
    """
    停止调度器
    
    Args:
        wait: 是否等待所有任务完成
    """
    if not self._running:
        return

    logger.info("停止调度器...")
    self._running = False
    self._stop_event.set()  # 通知所有执行器停止

    # 停止账号创建调度器
    if self.account_creation_scheduler:
        self.account_creation_scheduler.stop(wait=wait)

    if self._executor_pool:
        self._executor_pool.shutdown(wait=wait)
        self._executor_pool = None

    if hasattr(self, "_main_thread") and self._main_thread.is_alive():
        self._main_thread.join(timeout=10)

    logger.info("调度器已停止")
```

在 `Scheduler.get_status` 方法中添加状态信息：

```python
def get_status(self) -> dict[str, Any]:
    """
    获取调度器状态
    
    Returns:
        包含调度器状态信息的字典
    """
    device_status = self.device_pool.get_status_summary()

    pending_count = 0
    running_count = 0
    if self._task_instance_repo:
        pending_count = self._task_instance_repo.count_by_status(
            TaskStatus.PENDING.value
        )
        running_count = self._task_instance_repo.count_by_status(
            TaskStatus.RUNNING.value
        )

    status = {
        "running": self._running,
        "devices": device_status,
        "tasks": {
            "pending": pending_count,
            "running": running_count,
        },
    }
    
    # 添加账号创建调度器状态
    if self.account_creation_scheduler:
        status["account_creation"] = self.account_creation_scheduler.get_status()
    
    return status
```

**Step 2: 在主程序入口启用自动账号创建**

修改 `src/ptcgp_auto_v2/main.py` 中的守护模式启动：

```python
# 在守护模式启动代码中添加参数

def start_daemon(settings, args):
    """启动守护模式"""
    # ... 现有代码 ...
    
    scheduler = Scheduler(
        device_addresses=settings.device_addresses,
        config=SchedulerConfig(
            poll_interval=settings.poll_interval,
            max_workers=settings.max_workers,
            task_generation_interval=settings.task_generation_interval,
        ),
    )
    
    # 如果命令行参数启用了自动账号创建
    if getattr(args, 'auto_create_accounts', False):
        scheduler.enable_auto_account_creation = True
        scheduler.max_auto_accounts = getattr(args, 'max_accounts', 100)
        logger.info(f"已启用自动账号创建 (最大数量: {scheduler.max_auto_accounts})")
    
    scheduler.start()
    # ... 其余代码 ...
```

**Step 3: Commit**

```bash
git add src/ptcgp_auto_v2/core/scheduler.py src/ptcgp_auto_v2/main.py
git commit -m "feat: integrate account creation scheduler into main scheduler

- 在 Scheduler 中集成 AccountCreationScheduler
- 支持通过配置启用/禁用自动账号创建
- 在状态查询中显示账号创建状态"
```

---

## Task 4: 添加命令行参数支持

**Files:**
- Modify: `main_v2.py`

**Step 1: 添加命令行参数**

在 `main_v2.py` 的参数解析部分添加：

```python
# 在 create_parser() 函数中添加

def create_parser():
    parser = argparse.ArgumentParser(
        description="PTCGP Auto v2 - Pokemon TCG Pocket Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main_v2.py --daemon                          # 守护模式（普通调度）
  python main_v2.py --daemon --auto-create-accounts   # 守护模式（启用自动创建账号）
  python main_v2.py --daemon --max-accounts 200       # 设置最大账号数为 200
  python main_v2.py --task open_pack --account 1      # 执行单个任务
        """
    )
    
    # ... 现有参数 ...
    
    # 自动创建账号相关参数
    parser.add_argument(
        "--auto-create-accounts",
        action="store_true",
        help="启用自动创建小号功能（默认关闭）",
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=100,
        help="自动创建账号的最大数量上限（默认：100）",
    )
    
    return parser
```

**Step 2: 修改主函数传递参数**

```python
def main():
    args = create_parser().parse_args()
    
    # ... 现有代码 ...
    
    if args.daemon:
        # 将参数传递给 scheduler
        scheduler = Scheduler(
            device_addresses=settings.device_addresses,
            config=SchedulerConfig(
                poll_interval=settings.poll_interval,
                max_workers=settings.max_workers,
                task_generation_interval=settings.task_generation_interval,
            ),
        )
        
        # 配置自动账号创建
        if args.auto_create_accounts:
            scheduler.enable_auto_account_creation = True
            scheduler.max_auto_accounts = args.max_accounts
            logger.info(f"已启用自动账号创建，最大数量: {args.max_accounts}")
        
        scheduler.run()
    
    # ... 其余代码 ...
```

**Step 3: Commit**

```bash
git add main_v2.py
git commit -m "feat: add CLI arguments for auto account creation

- 添加 --auto-create-accounts 参数启用功能
- 添加 --max-accounts 参数设置上限"
```

---

## Task 5: 更新 Web 界面支持

**Files:**
- Modify: `src/ptcgp_auto_v2/web/app.py`

**Step 1: 添加账号创建调度器 API 端点**

在 Web 应用中添加状态查询和控制端点：

```python
# 在 app.py 中添加

@app.get("/api/account-creation/status")
def get_account_creation_status():
    """获取账号创建调度器状态"""
    if not scheduler or not scheduler.account_creation_scheduler:
        return {
            "enabled": False,
            "message": "自动账号创建未启用",
        }
    
    return {
        "enabled": True,
        **scheduler.account_creation_scheduler.get_status()
    }

@app.post("/api/account-creation/toggle")
def toggle_account_creation(enable: bool, max_accounts: int = 100):
    """启用/禁用自动账号创建"""
    global scheduler
    
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未启动")
    
    if enable:
        scheduler.enable_auto_account_creation = True
        scheduler.max_auto_accounts = max_accounts
        if not scheduler.account_creation_scheduler:
            from ptcgp_auto_v2.core.account_creation_scheduler import AccountCreationScheduler
            scheduler.account_creation_scheduler = AccountCreationScheduler(
                max_accounts=max_accounts,
                check_interval=scheduler.config.task_generation_interval,
            )
        scheduler.account_creation_scheduler.start()
        return {"status": "enabled", "max_accounts": max_accounts}
    else:
        scheduler.enable_auto_account_creation = False
        if scheduler.account_creation_scheduler:
            scheduler.account_creation_scheduler.stop()
            scheduler.account_creation_scheduler = None
        return {"status": "disabled"}
```

**Step 2: Commit**

```bash
git add src/ptcgp_auto_v2/web/app.py
git commit -m "feat: add web API for account creation scheduler

- 添加 /api/account-creation/status 查询状态
- 添加 /api/account-creation/toggle 启用/禁用功能"
```

---

## Task 6: 添加日志和监控

**Files:**
- Modify: `src/ptcgp_auto_v2/core/account_creation_scheduler.py`

**Step 1: 添加更详细的日志**

已在 Task 2 的代码中包含基础日志，现在添加更多监控点：

```python
# 在 _main_loop 方法中添加更详细的日志

def _main_loop(self):
    """主循环"""
    logger.info("账号创建调度器主循环已启动")
    
    while self._running:
        try:
            # 记录检查日志
            current_count = self._account_repo.count_all()
            logger.debug(f"检查账号创建条件: 当前 {current_count}/{self.max_accounts}")
            
            if self._should_create_account():
                logger.info("条件满足，开始尝试创建新账号")
                self._try_create_account()
            else:
                has_tasks = self._task_instance_repo.has_any_tasks_except_completed()
                logger.debug(f"跳过创建: has_tasks={has_tasks}, count={current_count}/{self.max_accounts}")
                
        except Exception as e:
            logger.exception(f"账号创建调度器异常: {e}")

        # 等待检查间隔或停止信号
        if self._stop_event.wait(timeout=self.check_interval):
            break
    
    logger.info("账号创建调度器主循环已结束")
```

**Step 2: Commit**

```bash
git add src/ptcgp_auto_v2/core/account_creation_scheduler.py
git commit -m "chore: enhance logging for account creation scheduler

- 添加详细的调试日志
- 记录每次检查的条件状态"
```

---

## 验证清单

### 功能验证

1. **检查方法正确性**
   - [ ] `has_any_tasks_except_completed` 正确识别非 completed 任务
   - [ ] `count_all` 正确统计账号数量

2. **调度器行为**
   - [ ] 当存在 pending/running 任务时，不创建账号
   - [ ] 当账号数达到上限时，停止创建
   - [ ] 系统空闲时，自动创新账号

3. **创建流程**
   - [ ] 正确处理已管理账号（更新 XML 后重置）
   - [ ] 正确处理未管理账号（直接重置）
   - [ ] init_account 任务成功执行
   - [ ] 创建成功后保存账号信息

4. **集成测试**
   - [ ] 命令行参数正确传递
   - [ ] Web API 正常响应
   - [ ] 调度器启动/停止正常

### 运行测试

```bash
# 测试 1: 检查仓库方法
python -c "
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository, AccountRepository
task_repo = TaskInstanceRepository()
account_repo = AccountRepository()
print(f'Has tasks: {task_repo.has_any_tasks_except_completed()}')
print(f'Account count: {account_repo.count_all()}')
"

# 测试 2: 启动调度器（不带自动创建）
python main_v2.py --daemon

# 测试 3: 启动调度器（带自动创建）
python main_v2.py --daemon --auto-create-accounts --max-accounts 100

# 测试 4: 查询状态
curl http://localhost:8000/api/account-creation/status
```

---

## 文档更新

完成后更新以下文档：

1. **README.md** - 添加自动账号创建功能说明
2. **CLAUDE.md** - 更新架构说明，包含 AccountCreationScheduler
3. **docs/needs/03-定时创建小号机制.md** - 标记为已完成

---

**计划完成时间:** 约 2-3 小时
**依赖:** 现有 init_account 任务、账号同步机制、设备发现
**风险:** 设备兼容性、游戏界面变化可能影响 init_account 任务成功率
