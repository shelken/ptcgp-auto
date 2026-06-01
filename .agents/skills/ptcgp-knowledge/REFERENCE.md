# PTCGP Knowledge Reference

## 当前工具

```text
.agents/skills/ptcgp-knowledge/scripts/raenonx_events.py
```

用途：查询 RaenonX PTCGP 活动 brief。

主数据接口：

```text
https://ptcgp.raenonx.cc/api/data/event-brief
```

来源页面：

```text
https://ptcgp.raenonx.cc/zh/event
```

中文名来源：脚本从活动页提取 `dpl`，再请求：

```text
https://ptcgp.raenonx.cc/zh/event?_rsc=1&dpl=<deployment-id>
```

## 常用命令

```bash
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state current --page 1 --limit 20 --json
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state upcoming --page 1 --limit 20 --json
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state expired --page 1 --limit 20 --json
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --type soloBattle --page 1 --limit 10 --json
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py get --type wonderPickFree --id SC_GC_2605000_01 --json
```

## 参数

- `list`：分页列出活动。
- `get`：按 `(type, id)` 查询单条活动。
- `--state current|upcoming|future|expired|permanent`：按状态筛选。
- `--type <event type>`：按 RaenonX event type 筛选。
- `--page <n>`：页码，最小 1。
- `--limit <n>`：每页数量，1 到 100，默认 20。
- `--sort start-desc|start-asc|end-desc|end-asc`：排序，默认 `start-desc`。
- `--json`：输出 JSON。

## 状态定义

- `current`：`start <= now < end`
- `upcoming`：未来 30 天内开始
- `future`：30 天后开始
- `expired`：已结束
- `permanent`：结束时间缺失或为 0

## 输出字段

- `type`：RaenonX 活动类型，如 `soloBattle`、`missionGroup`、`wonderPickFree`。
- `id`：活动 ID。
- `name`：中文名，来自 RSC i18n 字典。
- `nameI18nId`：活动名称字典 key。
- `titleFallback`：`name` 缺失时用于展示的标题。
- `state`：当前计算状态。
- `startEpoch` / `endEpoch`：秒级时间戳。
- `startLocal` / `endLocal`：本机本地时间字符串。
- `rewardSummary`：通用奖励摘要，只取 `type`、`id`、`count`。
- `relatedCardIds`：关联的 `PK_...` / `TR_...` 卡牌 ID。
- `sourceUrl`：来源页面。
- `warnings`：解析 warning。

## Warning 含义

- `missing nameI18nId`：源数据没有活动名称 key，通常用 `id` 或 `seasonId` 展示。
- `missing i18n message: <key>`：活动数据有 key，但 RSC 字典里没找到翻译。
- `无法从 RaenonX 活动页提取 dpl`：活动数据仍可用，但中文名可能缺失。

## 排错

- HTTP 非 200：站点不可达或接口变更，保留错误原文。
- 顶层不是 list：`/api/data/event-brief` schema 变化，需要重新检查接口。
- `get` 找不到活动：确认必须同时传 `--type` 和 `--id`；某些活动共享同一个 `id`。
- 中文名缺失：先使用 `titleFallback` 回答，并说明 warning。

## 数据原则

- 游戏可直接获取的主数据不从网站覆盖。
- 活动日历和活动奖励摘要可用 RaenonX。
- 回答事实时附 `sourceUrl`。
- 不抓图片、不保存图片、不分发图片。
