# 任务实例上次执行耗时实施计划

## 关联设计文档

- `docs/plans/2026-03-07-task-duration-design.md`

## 目标

基于已确认设计，为 `TaskInstance` 增加上次执行耗时能力，并在 Web 任务列表中展示和排序，保证：

- 耗时只统计当前任务实例自身执行时间
- 任何结束态都能记录耗时
- Web 列表支持查看与排序
- 实现过程中不复制状态逻辑，不让执行器分支膨胀

## 阶段拆分

### Phase 1：模型与仓储收敛

目标：

- 新增 `TaskInstance.last_duration_seconds`
- 更新 `to_dict()` 与仓储 `update()` 的字段同步

任务：

1. 修改 `src/ptcgp_auto_v2/db/models/task_instance.py`
2. 修改 `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
3. 检查数据库初始化自动补列路径是否无需额外迁移

验收：

- 新字段可以被模型实例读写
- `save()` 后字段会落库

### Phase 2：执行器耗时链路收敛

目标：

- 在不污染前置任务耗时的前提下记录当前任务实例自身耗时
- 结束态统一通过 `_apply_task_status()` 写入

任务：

1. 在 `src/ptcgp_auto_v2/core/executor.py` 中封装当前任务执行计时 helper
2. 让 `_execute_task_with_prerequisites()` 返回累计后的 `duration_seconds`
3. 扩展 `_apply_task_status()` 接收并写入 `duration_seconds`
4. 收敛单任务执行器与批量执行器的结束态耗时透传
5. 明确未进入任务执行即失败的路径写 `0`

验收：

- 前置任务耗时不计入主任务
- 主任务两次执行的耗时能正确累计
- 账号切换失败等路径写入 `0`

### Phase 3：Web 展示与排序

目标：

- 任务列表新增“上次耗时”列
- 支持按 `last_duration_seconds` 排序
- 耗时显示风格与现有相对时间一致，使用前端统一增强后的人性化文案

任务：

1. 修改 `src/ptcgp_auto_v2/web/services/task_service.py`
2. 修改 `src/ptcgp_auto_v2/web/queries/task_queries.py`
3. 修改 `src/ptcgp_auto_v2/web/templates/partials/task_list.html`
4. 扩展 `src/ptcgp_auto_v2/web/static/js/modules/relative_time.js` 或同层统一模块，增加时长格式化能力
5. 复用现有排序机制，不新增独立接口
6. 处理 `NULL` 排序放最后

验收：

- 列表显示人性化时长文案或 `-`
- 升序/降序可用
- 默认排序保持不变

### Phase 4：测试补齐

目标：

- 为新字段、执行器边界和 Web 排序提供回归保护

任务：

1. 补 `src/ptcgp_auto_v2/tests/core/test_executor_apply_status.py`
2. 新增或补齐执行器链路测试
3. 补 Web 查询/服务排序测试
4. 补模板渲染或上下文格式化测试

验收：

- 关键结束态、前置任务边界、`NULL` 排序行为都有测试

### Phase 5：回归验证

目标：

- 确认实际行为与设计一致

任务：

1. 运行与本次改动相关的单元测试
2. 检查任务列表展示结果
3. 检查排序参数是否正确传递
4. 检查老数据兼容行为

验收：

- 相关测试全部通过
- 无明显重复逻辑或多余分支

## 实施顺序要求

必须按以下顺序推进，避免边写边散：

1. 先改模型和仓储
2. 再改执行器主链路
3. 再接 Web 展示和排序
4. 最后补测试与回归验证

## 风险点

### 风险 1：把前置任务时间混入主任务

规避方式：

- 计时边界只包当前任务 `task.execute(...)`
- 不以 `running` 状态时间作为耗时来源

### 风险 2：状态落库逻辑分叉

规避方式：

- 继续以 `_apply_task_status()` 作为唯一结束态落库入口

### 风险 3：Web 展示逻辑写进模板

规避方式：

- 模板只消费格式化后的展示值，不承担复杂格式转换

## 完成定义

满足以下条件才算完成：

- 数据库中 `task_instances` 新增 `last_duration_seconds`
- 执行器对结束态正确写入耗时
- 前置任务时间未污染主任务耗时
- Web 列表新增展示与排序
- 相关测试通过
