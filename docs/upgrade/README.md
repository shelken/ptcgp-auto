# 依赖升级 SOP

## 入口

1. 先运行 `.agents/skills/dependency-upgrade/scripts/outdated.sh`
2. 先把过期依赖清单和分组建议给用户确认
3. 只对用户允许的分组继续往下做
4. 用 `.agents/skills/dependency-upgrade/scripts/prepare_report.sh <主题>` 创建当日报告，并自动清理旧日期文档

## 报告规则

- 升级报告统一放 `docs/upgrade/`
- 文件名统一 `YYYY-MM-DD-主题.md`
- 旧日期报告直接删，历史交给 git
- 报告里只写本次分组、影响面、验证结果和结论

## 分组规则

- 同一链路、同一生态一起升
- 不相关且低风险的小包可以一组
- 关键依赖如果影响面大，单独一组，单独一份报告，单独一个 PR

## 验证规则

- Python 基础检查：`.agents/skills/dependency-upgrade/scripts/verify.sh main`
- Web / 数据链路：`.agents/skills/dependency-upgrade/scripts/verify.sh web`
- 图像链路：`.agents/skills/dependency-upgrade/scripts/verify.sh image`
- 模型链路：`.agents/skills/dependency-upgrade/scripts/verify.sh model`
- 训练子项目：`.agents/skills/dependency-upgrade/scripts/verify.sh training`

## 提交和 PR

- 一组升级只做一类事
- 一组升级对应一个 commit 和一个 PR
- Agent 负责调研、验证、写报告、提交，并把相关 PR 整理后告知用户
- 用户负责审阅
