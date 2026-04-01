---
name: dependency-upgrade
description: Use when doing dependency upgrades, outdated dependency audits, grouped upgrade PR prep, upgrade report writing, or dependency governance cleanup. Trigger on requests like "升级依赖", "检查过期依赖", "稳健升级", "分组升级", "升级报告", or "依赖治理".
---

## 硬规则

1. 报告统一放 `docs/upgrade/`，文件名用 `日期-主题.md`
2. 先跑 `./scripts/outdated.sh` 出清单，再停下来给用户确认，只继续处理用户允许的分组
3. 开新一组升级前，先用 `./scripts/prepare_report.sh <主题>` 清旧日期报告
4. 同链路一起升，不相关低风险可合并，关键大范围单独一个 PR
5. 每组升级都要先查实际用法和官方变更，再升级，再验证
6. Agent 负责把相关 commit 和 PR 都准备好并告知用户，用户负责审阅

## 固定脚本

- `./scripts/prepare_report.sh <主题>`
- `./scripts/outdated.sh [main|training|all]`
- `./scripts/verify.sh <main|web|image|model|training|all>`

## 最短流程

1. 跑 `outdated.sh`
2. 把清单和建议分组给用户确认
3. 跑 `prepare_report.sh <主题>`
4. 按分组查官方变更和仓库真实用法
5. 只升用户允许的一组
6. 跑对应 `verify.sh`
7. 更新 `docs/upgrade/日期-主题.md`
8. 一个分组一个 commit 和一个 PR，整理后告诉用户审阅
