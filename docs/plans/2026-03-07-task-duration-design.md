# 任务实例上次执行耗时设计文档

## 原始需求（用户原话）

> src/ptcgp_auto_v2/core/task_base.py
> src/ptcgp_auto_v2/web/templates/partials/task_list.html
> src/ptcgp_auto_v2/db/models/task_instance.py
>
> 希望增加一个字段用来保存每次任务从开始到完成消耗的时间，也就是记录上次任务的持续时间，不止成功完成，任何状态退出均记录这个持续时间。

## 用户澄清与约束（原话记录）

### 澄清 1：耗时统计范围

**用户原话：**
> 2

**上下文：**
- 选项 2 为“当前 task instance 自身耗时”
- 不包含前置任务链耗时

**结论：**
- `last_duration_seconds` 只统计当前任务实例自身执行耗时
- 前置任务各自单独记录，不并入主任务

### 澄清 2：存储单位

**用户原话：**
> 1

**上下文：**
- 选项 1 为“整数秒”

**结论：**
- 新字段以整数秒落库

### 澄清 3：代码质量要求

**用户原话：**
> 不过你一定要设计好代码，严格遵守代码质量，不要出现代码逻辑重复，能合并合并，编写过程中不要让代码膨胀

**结论：**
- 计时逻辑必须收敛到单一执行链路
- 状态落库保持单出口，禁止复制多份状态更新分支

### 澄清 4：Web 列表排序

**用户原话：**
> 还有，web列表你要加上排序。

**用户原话：**
> 是

**结论：**
- Web 列表新增“按上次耗时排序”
- 默认排序保持现状，不改为耗时排序

### 澄清 5：Web 显示方式

**用户原话：**
> 对了，你必须再看看如何显示消耗时间，要跟web页面相对时间的显示逻辑一样。更加人性化，而不是直接显示秒数。懂吗？

**结论：**
- 不能直接显示原始秒数，例如 `125s`
- 必须沿用当前 Web 相对时间相同的前端增强模式
- 展示为人性化时长文本，排序仍基于原始秒数

## 目标

在 `TaskInstance` 上增加“上次执行耗时”字段，并保证：

- 任何结束态都能写入该值，包括 `completed`、`failed`、`skipped`、`blocked`
- 该值语义稳定，明确表示“当前任务实例自身上次执行耗时”
- Web 任务列表能够展示并按该字段排序
- 实现不引入重复状态逻辑，不额外膨胀执行器分支

## 非目标

- 不记录完整历史耗时
- 不增加任务开始时间字段
- 不改变调度优先级或默认列表排序
- 不把前置任务时间合并到主任务

## 现状分析

### 数据模型

当前 [`src/ptcgp_auto_v2/db/models/task_instance.py`](src/ptcgp_auto_v2/db/models/task_instance.py) 只有：

- `status`
- `error_message`
- `last_completed_at`
- `next_run_at`

没有任何耗时字段。

### 状态落库

当前 [`src/ptcgp_auto_v2/core/executor.py`](src/ptcgp_auto_v2/core/executor.py) 中：

- `_apply_task_status()` 是状态写回数据库的主收口点
- `completed` 会写 `last_completed_at`
- `failed/skipped/blocked` 没有耗时记录逻辑

### 执行路径

当前任务执行的关键路径为：

1. 调度器将任务实例标记为 `running`
2. 执行器准备设备、账号上下文
3. `_execute_task_with_prerequisites()` 执行当前任务
4. 若需要前置任务，则递归执行前置任务，再回到当前任务继续执行
5. 外层根据结果调用 `_apply_task_status()` 写回结束态

问题在于：

- 如果从 `running` 状态开始计时，会把前置任务耗时混入当前任务
- 当前没有统一字段保存结束态耗时

## 方案选择

### 方案 A：仅新增 `last_duration_seconds`

- 在 `TaskInstance` 上新增 `last_duration_seconds: Optional[int]`
- 在执行器内存中记录当前任务执行耗时
- 结束态统一写回该字段

**优点：**
- 字段最少，语义清晰
- 不引入运行中状态持久化复杂度
- 最符合当前需求

**缺点：**
- 无法直接查看“最近一次开始时间”

### 方案 B：新增 `started_at + last_duration_seconds`

- 进入任务时先写 `started_at`
- 结束时计算并写 `last_duration_seconds`

**优点：**
- 便于后续展示运行中耗时

**缺点：**
- 字段膨胀
- 需要处理中断残留和运行中语义
- 超出当前需求

### 结论

采用方案 A。

## 最终设计

### 1. 数据模型

在 [`src/ptcgp_auto_v2/db/models/task_instance.py`](src/ptcgp_auto_v2/db/models/task_instance.py) 新增字段：

```python
last_duration_seconds: Optional[int] = Field(
    default=None,
    description="任务实例上一次自身执行耗时（秒）",
)
```

语义约束：

- 单位为整数秒
- 非负数
- `None` 表示从未产出过结束态耗时
- 始终表示最近一次结束执行的耗时

数据库兼容性：

- 项目当前 SQLite 初始化支持自动补列
- 本次新增字段无需单独引入复杂迁移方案

### 2. 计时边界

计时不以 `running` 状态为边界，而以“当前任务自身执行调用”为边界。

具体规则：

- 在 `_execute_task_with_prerequisites()` 内部，调用当前任务 `task.execute(...)` 前记录单调时钟
- `task.execute(...)` 返回后计算本次耗时秒数
- 如果当前任务先执行一次用于收集前置任务，再执行第二次 `skip_pre_hooks=True`，则两次耗时累加
- 递归进入前置任务时，前置任务自己计时；主任务不累计该段时间

这样可以保证：

- 主任务耗时不被前置任务污染
- 前置任务也能单独得到自己的上次耗时

### 3. 结果传递

不新增额外状态写回入口，继续复用当前执行链路。

设计方式：

- 在 `TaskResult.data` 中增加 `duration_seconds`
- `_execute_task_with_prerequisites()` 在返回 `TaskResult` 前将累计耗时写入 `result.data`
- 外层状态处理读取该值，透传给 `_apply_task_status()`

这样做的原因：

- 不修改 `Task` 子类接口
- 不在任务实现层引入耗时概念
- 保持耗时逻辑只存在于执行器层

### 4. 状态落库单出口

扩展 `_apply_task_status()`，增加参数：

```python
duration_seconds: Optional[int] = None
```

写回规则：

- `completed/failed/skipped/blocked`：若提供 `duration_seconds`，则写入 `last_duration_seconds`
- `pending/running`：不写 `last_duration_seconds`
- 对于未真正进入任务执行就失败的路径，例如账号切换失败，写入 `0`

这样可以保证：

- 所有结束态都满足“有记录”
- 旧有状态落库逻辑保持单出口
- 不会为了不同状态复制多份写库逻辑

### 5. 批量执行器与单任务执行器一致性

单任务执行器与批量执行器都必须复用相同的结束态写回逻辑。

要求：

- 不为批量执行器单独实现一套耗时落库分支
- 任务实际耗时均从 `_execute_task_with_prerequisites()` 返回
- 外层只负责把耗时透传到 `_apply_task_status()`

特殊情况：

- 批量执行器中账号切换失败时，所有被标记失败的任务都写入 `0`

### 6. Web 列表展示

在 [`src/ptcgp_auto_v2/web/services/task_service.py`](src/ptcgp_auto_v2/web/services/task_service.py) 中把 `last_duration_seconds` 透传到列表行数据。

在 [`src/ptcgp_auto_v2/web/templates/partials/task_list.html`](src/ptcgp_auto_v2/web/templates/partials/task_list.html) 中新增一列：

- 列名：`Last Duration`
- 显示规则：
  - 有值时显示人性化时长结果，例如 `2分钟`、`3小时`、`1天`
  - 无值时显示 `-`

模板层约束：

- 不在模板中堆积复杂秒数拆分逻辑
- 不在服务层直接输出 `125s` 这类硬编码字符串
- 参考当前 `relative-time` 的实现方式，在前端统一增强渲染
- 模板只提供原始秒数与 tooltip 所需原始值

具体设计：

- 新增类似 `.relative-time` 的时长展示类，例如 `.relative-duration`
- 模板写入 `data-seconds="{{ item.last_duration_seconds }}"` 与完整 tooltip
- 前端模块统一扫描并渲染人性化文案
- 排序仍然使用数据库中的原始 `last_duration_seconds`

人性化文案规则：

- 小于 60 秒：显示 `45秒`
- 小于 1 小时：显示 `2分钟`
- 小于 1 天：显示 `3小时`
- 大于等于 1 天：显示 `1天`

tooltip 规则：

- tooltip 显示精确时长，例如 `2分钟 5秒`、`1小时 3分钟`
- 精确时长文案可复用现有 locale 中的 `label_interval_days/hours/minutes/seconds`

### 7. Web 列表排序

在 [`src/ptcgp_auto_v2/web/queries/task_queries.py`](src/ptcgp_auto_v2/web/queries/task_queries.py) 中新增排序字段：

- `sort_by=last_duration_seconds`

排序规则：

- 支持升序与降序
- `NULL` 始终排最后
- 默认排序保持现状，不改为耗时排序

实现要求：

- 复用当前任务列表已有排序参数机制
- 不单独造新的排序接口

## 异常与边界处理

### 1. 前置任务链

- 主任务第一次执行只用于发现前置任务时，已产生的主任务自身耗时仍要保留
- 前置任务递归执行的耗时只归属前置任务自身
- 主任务第二次恢复执行时继续累计自身耗时

### 2. 未进入任务执行的失败

例如：

- 账号切换失败
- 执行器异常导致任务直接失败

处理规则：

- 由于没有真正进入任务执行，`last_duration_seconds` 写 `0`

### 3. 重新排队

当前 `_handle_requeue_in_result()` 会把任务重新置回 `pending`，不是结束态。

处理规则：

- `pending` 重排不写 `last_duration_seconds`
- 保留上一次结束态耗时

### 4. 手动重置与老数据

- 老数据新增字段后默认 `NULL`
- 手动重置 completed 等现有行为不强制清空 `last_duration_seconds`
- 字段表示“上一次结束执行耗时”，不是“当前是否完成”的派生值

## 代码去重原则

本次实现必须遵守以下收敛原则：

- 计时逻辑只放在执行器层，不放入各个 `Task` 子类
- 状态落库只通过 `_apply_task_status()` 完成
- 单任务执行器和批量执行器复用同一套耗时传递方式
- Web 仅负责透传、展示、排序，不承担业务计时逻辑
- 人性化时长展示复用现有相对时间的前端增强模式，不新增分散的模板拼接逻辑

## 测试设计

### 核心单测

需要补充或调整的测试包括：

1. `test_executor_apply_status`
   - 结束态写入 `last_duration_seconds`
   - `running/pending` 不覆盖该字段

2. 执行器链路测试
   - 前置任务耗时不计入主任务
   - 当前任务两次执行时耗时可累计
   - 账号切换失败时写入 `0`

3. Web 查询/服务测试
   - 列表上下文包含 `last_duration_seconds`
   - 新排序字段可正常生效
   - `NULL` 排序位置符合预期

4. 模板渲染测试
   - 有值显示人性化时长文案
   - 无值显示 `-`

5. 前端时长格式化测试
   - 秒、分钟、小时、天四个区间输出符合预期
   - tooltip 精确时长符合预期

## 验收标准

- `TaskInstance` 成功新增 `last_duration_seconds`
- 任一任务结束后都能得到正确的上次自身耗时
- 主任务耗时不包含前置任务耗时
- Web 列表新增“上次耗时”列并支持排序
- 默认列表排序不变
- 状态落库逻辑没有新增重复分支
- 测试覆盖关键边界

## 实施建议

实现时应按以下顺序推进：

1. 先补模型与仓储更新
2. 再收敛执行器耗时逻辑
3. 然后补 Web 服务与排序
4. 最后补测试，验证前置任务边界与排序行为
