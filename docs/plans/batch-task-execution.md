# 任务批量执行改造方案

## 问题分析

### 当前问题

1. **任务拆分过度**：`task_plan` 中的多个 `task_type` 被拆分成独立的 `task_instance`，每个任务独立调度
2. **频繁账号切换**：设备完成一个任务后可能被分配到其他账号的任务，导致频繁切换账号
3. **无法保证顺序**：无法保证同一账号的任务按 `task_plan.task_types` 数组顺序执行

### 期望行为

- 同一账号的所有任务应该在**同一设备上连续执行**
- 任务按 `task_plan.task_types` 数组**顺序执行**
- 避免不必要的账号切换，提高执行效率

## 改造方案

### 核心思路

将调度模式从「单个 TaskInstance 调度」改为「账号级批量任务调度」：

```
改造前: 获取单个任务 → 分配到设备 → 执行 → 释放设备 → 获取下一个任务（可能是其他账号）

改造后: 获取账号的所有待执行任务 → 分配到设备 → 按顺序执行所有任务 → 释放设备
```

### 需要修改的文件

| 文件 | 改动内容 |
|------|---------|
| `scheduler.py` | 新增批量调度方法，修改主循环 |
| `executor.py` | 新增 `AccountBatchExecutor` 类 |
| `repositories.py` | 新增查询方法 |

### 详细设计

#### 1. scheduler.py 改造

**新增方法：**

```python
def _get_next_account_batch(self) -> Optional[tuple[int, List["TaskInstance"]]]:
    """获取下一个账号及其所有待执行任务（按 task_plan 顺序）"""

def _order_tasks_by_plan(self, account_id: int, tasks: List["TaskInstance"]) -> List["TaskInstance"]:
    """按照 task_plan.task_types 顺序排列任务"""

def _dispatch_account_batch(self, account_id: int, task_instances: List["TaskInstance"]):
    """批量分配账号的所有任务到同一设备"""
```

**修改主循环：**

```python
def _main_loop(self):
    while self._running:
        self._generate_pending_tasks()

        if self.device_pool.available_count == 0:
            time.sleep(self.config.poll_interval)
            continue

        # 改为批量获取
        batch = self._get_next_account_batch()
        if not batch:
            time.sleep(self.config.poll_interval)
            continue

        account_id, task_instances = batch
        self._dispatch_account_batch(account_id, task_instances)
```

#### 2. executor.py 改造

**新增 `AccountBatchExecutor` 类：**

```python
class AccountBatchExecutor:
    """
    账号批量任务执行器

    在一个设备上顺序执行账号的所有任务，避免频繁切换账号。
    """
    def __init__(self, device, account_id, task_instances, device_pool, config):
        self.device = device
        self.account_id = account_id
        self.task_instances = task_instances  # 按顺序排列的任务列表
        ...

    def run(self):
        # 1. 初始化组件（ADB、OCR 等）
        self._init_components()

        # 2. 切换到目标账号（如需要）
        if not self._switch_account():
            # 标记所有任务失败
            return

        # 3. 顺序执行所有任务
        for task_instance in self.task_instances:
            if self._should_stop():
                break
            self._execute_single_task(task_instance)

        # 4. 释放设备
        self.device_pool.release(self.device)
```

#### 3. repositories.py 改造

**新增查询方法：**

```python
def get_accounts_with_pending_tasks(self) -> List[int]:
    """获取所有有待执行任务的账号 ID 列表"""

def has_running_tasks(self, account_id: int) -> bool:
    """检查账号是否有正在执行的任务"""

def get_pending_tasks_by_account(self, account_id: int) -> List[TaskInstance]:
    """获取账号的所有待执行任务"""
```

## 执行顺序保证

任务执行顺序由以下逻辑保证：

```python
def _order_tasks_by_plan(self, account_id, tasks):
    account = self._account_repo.get_by_id(account_id)
    if not account.task_plan:
        return sorted(tasks, key=lambda x: x.created_at)

    # 按照 task_plan.task_types 数组顺序排列
    plan_order = {task_type: idx for idx, task_type in enumerate(account.task_plan.task_types)}
    return sorted(tasks, key=lambda x: plan_order.get(x.task_type, 999))
```

例如，如果 `task_plan.task_types = ["fetch_account_info", "open_pack", "send_gift"]`，则任务会按此顺序执行。

## 优势

1. **减少账号切换**：同一账号的所有任务连续执行
2. **保证执行顺序**：严格按照 `task_plan` 定义的顺序
3. **提高效率**：避免重复的账号登录/切换操作
4. **资源优化**：设备利用率更高

## 验证方式

1. 语法检查所有修改文件
2. 单元测试：验证任务排序逻辑
3. 集成测试：
   - 验证同一账号的任务在同一设备上连续执行
   - 验证任务按 `task_plan` 顺序执行
   - 验证多账号并发执行不冲突

## 设计决策

### 1. 任务失败处理

**策略**：失败任务标记为 `failed`，继续执行后续任务

```python
for task_instance in self.task_instances:
    try:
        self._execute_single_task(task_instance)
    except Exception as e:
        # 标记失败，但继续执行后续任务
        task_instance.status = TaskStatus.FAILED.value
        task_instance.error_message = str(e)
        task_instance.save()
        logger.error(f"任务 {task_instance.task_type} 失败: {e}，继续执行后续任务")
        continue
```

### 2. 前置任务处理

**策略**：自动检测并插入到批量任务开头

```python
def _get_next_account_batch(self):
    # 获取账号的待执行任务
    pending_tasks = self._get_pending_tasks_by_account(account_id)

    # 检查是否需要前置任务
    prerequisite_type = self._check_prerequisites(account)
    if prerequisite_type:
        # 将前置任务插入到任务列表开头
        prereq_instance = self._ensure_prerequisite_task(account_id, prerequisite_type)
        if prereq_instance not in pending_tasks:
            pending_tasks.insert(0, prereq_instance)

    # 按 task_plan 顺序排列
    return self._order_tasks_by_plan(account_id, pending_tasks)
```

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `src/ptcgp_auto_v2/core/scheduler.py` | 新增批量调度方法，修改主循环 |
| `src/ptcgp_auto_v2/core/executor.py` | 新增 `AccountBatchExecutor` 类，修改 `run_executor` 函数 |
| `src/ptcgp_auto_v2/db/repositories.py` | 新增 `get_accounts_with_pending_tasks`、`has_running_tasks`、`get_pending_tasks_by_account` 方法 |
