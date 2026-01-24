# Task Plan: v2 模块简化与封装

## Goal
在不触碰 v1 的前提下，重构 v2 模块以消除重复逻辑、减少跨模块细节操作，并通过清晰的模块封装提供可复用的高内聚接口。

## Current Phase
Phase 3

## Phases

### Phase 1: Requirements & Discovery
- [x] 理解用户诉求（仅限 v2）
- [x] 识别当前重复逻辑与跨模块耦合点
- [x] 将发现记录到 findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] 设计模块边界与职责划分
- [x] 明确可复用的封装函数/类
- [x] 记录关键决策与权衡
- **Status:** complete

### Phase 3: Implementation
- [x] 按计划逐步重构 v2
- [x] 以最小可审阅变更实现封装
- [ ] 如涉及非平凡逻辑，补充/更新测试
- **Status:** in_progress

### Phase 4: Testing & Verification
- [ ] 验证功能保持一致
- [ ] 将测试与人工验证记录到 progress.md
- [ ] 修复发现的问题
- **Status:** pending

### Phase 5: Delivery
- [ ] 汇总改动与影响范围
- [ ] 给出验证建议与后续建议
- [ ] 向用户交付
- **Status:** pending

## Key Questions
1. v2 中哪些模块最常直接操作 adb/template/ocr 细节？
2. 当前最明显的重复逻辑集中在哪些文件？
3. 现有工具与封装是否已有可复用的入口？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 仅重构 v2 | 明确不触碰 v1 逻辑与代码边界 |
| 优先 open_pack | 用户明确优先级 |
| 不新增通用模块 | 用户要求仅改现有 utils/infra |
| TEXT_PATTERNS 仅说明 | 用户希望先“介绍下”而非调整结构 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- 严格限制在 src/ptcgp_auto_v2
- 不触碰 v1 代码
- 2026-01-24：继续检查 infra 与 core 简化重构点
