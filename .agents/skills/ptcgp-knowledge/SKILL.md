---
name: ptcgp-knowledge
description: Query external Pokémon TCG Pocket knowledge sources for facts not directly available from game MemoryDatabase or ptcgp-assets. Use when user asks about PTCGP events, activity calendars, event rewards, rules, mechanics, or externally curated game facts.
---

# PTCGP Knowledge

## Quick start

查当前活动：

```bash
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state current --page 1 --limit 20 --json
```

查近期活动：

```bash
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state upcoming --page 1 --limit 20 --json
```

查历史活动：

```bash
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py list --state expired --page 1 --limit 20 --json
```

查单个活动：

```bash
uv run python .agents/skills/ptcgp-knowledge/scripts/raenonx_events.py get --type wonderPickFree --id SC_GC_2605000_01 --json
```

## Workflows

### 回答活动问题

1. 先调用 `raenonx_events.py`，不要凭记忆回答。
2. 按用户问题选择 `current`、`upcoming`、`expired` 或 `get`。
3. 大量列表必须使用 `--page` / `--limit`，不要全量 dump。
4. 回答中写明 `sourceUrl`。
5. 如果脚本返回 `warnings`，回答中说明数据可能不完整。

### 判断数据来源

- 卡牌、系列、包、本地化：优先 MemoryDatabase / ptcgp-assets。
- 活动日历、活动奖励、活动状态：用本 skill 的 RaenonX 脚本。
- 规则/机制说明：先查外部来源并附链接；当前暂无自动脚本。

## Rules

- 不抓取或分发图片。
- 不用外部网站覆盖游戏主数据。
- 不静默合并冲突事实。
- 不使用 `all` 这类无分页输出。

## Reference

更多字段、状态、warning 和排错说明见 [REFERENCE.md](REFERENCE.md)。
