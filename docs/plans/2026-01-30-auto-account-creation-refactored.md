# 自动创建小号机制实现计划（重构版）

**状态:** 已实施完成
**重构日期:** 2026-01-30

---

## 变更说明

**原方案（已废弃）:**
- 使用独立的 `AccountCreationScheduler` 组件
- 需要复杂的调度器协调机制
- 存在设备竞争和任务标记问题

**新方案（当前实现）:**
- 完全由主调度器接管自动创建功能
- 无需独立调度器，简化架构
- 天然支持断点续传

---

## 新方案架构

### 核心机制

**主调度器集成:**
```
主调度器主循环:
├─ 检查空闲设备
├─ 检查账号数 < 上限  
├─ 是否需要创建新账号？
│   ├─ 是: 重置一个空闲设备环境
│   ├─ 游戏自动进入新账号创建流程
│   └─ 等待账号被提取（下次 sync）
├─ 正常任务分配（含断点续传）
└─ 循环
```

**断点续传:**
- 每个新账号创建后自动生成 `init_account` 任务（pending）
- 调度器优先检查 `init_account` 状态
- 未完成时只执行 `init_account`，跳过其他任务
- 完成后自动分配 base 计划

---

## 实施内容

### 已完成的修改

#### 1. Scheduler 配置扩展
**文件:** `src/ptcgp_auto_v2/core/scheduler.py`

**修改:**
- `SchedulerConfig` 添加 `auto_create_accounts: bool = False`
- `SchedulerConfig` 添加 `max_accounts: int = 100`

#### 2. 断点续传逻辑
**文件:** `src/ptcgp_auto_v2/core/scheduler.py`

**修改:** `_get_next_account_batch()` 方法
- 检查账号是否有未完成 `init_account` 任务
- 如有，只返回 `init_account`，跳过其他任务
- 新增辅助方法 `_get_incomplete_init_task()`

#### 3. 自动创建触发逻辑
**文件:** `src/ptcgp_auto_v2/core/account_creation.py`（新增）

**功能:** `check_and_trigger_account_creation()`
- 主循环每轮检查
- 条件满足时重置设备环境
- 游戏自动进入新账号流程

**文件:** `src/ptcgp_auto_v2/core/scheduler.py`

**修改:**
- 添加 `_has_creating_account()` 方法
- 主循环调用触发函数

#### 4. init_account 完成处理
**文件:** `src/ptcgp_auto_v2/tasks/init_account.py`

**修改:** `on_complete()` 方法
- 成功后自动分配 base 计划
- 添加 `_assign_base_plan()` 辅助方法

#### 5. 账号创建控制
**文件:** `src/ptcgp_auto_v2/db/repositories/account_repository.py`

**修改:** `create()` 方法
- 添加 `auto_assign_plan: bool = True` 参数
- 新账号初始化时设为 False

#### 6. 命令行参数（保留）
**文件:** `src/ptcgp_auto_v2/main.py`

**保留:**
- `--auto-create-accounts`
- `--max-accounts`

**传递:** 参数传递给 `SchedulerConfig`

---

## 工作流程

### 新账号创建完整流程

```
1. 主调度器检测:
   - 空闲设备 > 0
   - 账号数 < max_accounts
   - 无正在创建的账号
   
2. 触发创建:
   - 获取空闲设备
   - reset_game_environment()
   - restart_app()
   - 归还设备

3. 设备状态:
   - 游戏进入新账号创建界面
   - 等待用户交互或自动流程

4. 账号提取:
   - AccountSyncer 检测到新 deviceAccount
   - 创建 Account 记录（无计划）
   - 生成 init_account 任务（pending）

5. 任务分配（断点续传）:
   - 调度器识别未完成 init_account
   - 只分配 init_account 任务
   - 执行初始化流程

6. 初始化完成:
   - init_account.on_complete() 分配 base 计划
   - 后续任务正常生成和执行
```

### 断点续传场景

**场景1: 初始化中断**
```
- init_account 执行到一半被中断
- 任务状态: running/pending
- 下次调度: 只分配 init_account，继续执行
- 其他任务: 被屏蔽直到 init_account 完成
```

**场景2: 设备重启**
```
- 系统重启后恢复
- 检测到未完成 init_account
- 自动继续初始化流程
- 无需人工干预
```

---

## 优点

1. **架构简化** - 无需独立调度器，减少协调复杂度
2. **断点续传** - 天然支持，基于 TaskInstance 状态
3. **无设备竞争** - 主调度器统一管理设备
4. **可靠性高** - 即使中断也能自动恢复
5. **易于维护** - 代码集中，逻辑清晰

---

## 配置使用

### 启用自动创建

```bash
python main_v2.py --daemon --auto-create-accounts --max-accounts 100
```

### 禁用自动创建（默认）

```bash
python main_v2.py --daemon
```

---

## 注意事项

1. **首次启动** - 需要手动点击游戏界面进入新账号流程
2. **设备要求** - 需要 Root 权限才能重置环境
3. **上限控制** - 达到 max_accounts 后自动停止创建
4. **失败处理** - 创建失败会记录日志，不会无限重试

---

## 相关文件

- `src/ptcgp_auto_v2/core/scheduler.py` - 主调度器逻辑
- `src/ptcgp_auto_v2/core/account_creation.py` - 自动创建触发
- `src/ptcgp_auto_v2/tasks/init_account.py` - 初始化任务
- `src/ptcgp_auto_v2/db/repositories/account_repository.py` - 账号仓库
- `src/ptcgp_auto_v2/main.py` - 命令行参数

---

## 废弃文件

以下文件不再使用（原独立调度器）:
- ~~`src/ptcgp_auto_v2/core/account_creation_scheduler.py`~~
