---
name: analyze-production-failures
description: Analyzes production failures by syncing data from yuuko, Use when the user mentions yuuko, production data, 通知表, 失败任务, data/logs, or 错误任务分析.
---

<objective>
从 yuuko 同步最新生产数据，分析通知表与任务状态错误，结合失败任务 JSONL 日志和源码定位问题，并输出可执行的修改建议报告。这个 skill 先做数据分析和定位，不先改代码。
</objective>

<quick_start>
> **时间范围**：若用户没指定时间范围，默认分析最近 **6 小时** 内的失败。
> 可以通过 `sqlite3` 的 `datetime(created_at) > datetime('now', '-6 hours')` 限定。

直接同步 yuuko 生产数据：

```bash
rsync -avhP yuuko.local:~/Code/MyRepo/ptcgp-auto/data ./
```

然后优先看三个位置：

- `data/ptcgp_v2.db`
- `data/logs/*.jsonl`
- `src/ptcgp_auto_v2/tasks/`
</quick_start>

<context>
只分析必要数据，不读取敏感 XML、密钥、token、API key 内容。涉及敏感文件时，只看结构、元数据、文件名、字段名或条目数量。

目录职责：

- `data/ptcgp_v2.db`：生产任务、通知、账号、运行状态主数据
- `data/logs/*.jsonl`：失败任务切片日志，首行是 summary，后续是结构化日志事件
- `.e2e-logs/<case>/<profile>/`：E2E 运行日志与 trace
- `src/ptcgp_auto_v2/tasks/`：任务页面流、动作逻辑、前置任务链
- `src/ptcgp_auto_v2/core/`：调度器、执行器、任务生命周期、状态收口
- `src/ptcgp_auto_v2/infra/`：ADB、OCR、通知、账号切换、日志持久化等基础设施
</context>

<known_patterns>
已知失败模式速查（优先匹配，减少重复排查）：

### 超过最大迭代次数
- **含义**：任务在某个页面循环超过迭代上限（150/180/200 不等）
- **常见根因**：网络连接问题（游戏未加载、卡请求、超时无响应）
- **排查路径**：优先翻日志中的 OCR 输出，看是否有网络错误文字（"通信错误"、"连接失败"、"再试一次"）或长时间没有有效 OCR 结果
- **跳过条件**：OCR 连续 3+ 轮只有 "9"@(44,164) 之类碎片化文字、无关键页面文字 → 大概率断网/卡加载

### 连续 N 次停留在同一页面: gift_select_card
- **含义**：选卡页面停留超限
- **常见根因**：游戏卡死/崩溃 — 模拟器端 App 失去响应，OCR 返回同样结果
- **已知引用**：GitHub issue 有记录（游戏长期运行后内存泄漏导致卡死）
- **排查路径**：检查 OCR 是否每轮完全一致（时间戳不同但文字坐标相同）→ 确认是游戏僵死而不是逻辑问题

### 连续 N 次停留在同一页面: unknown
- **含义**：页面检测器无法匹配任何已注册规则
- **典型场景**：
  1. 游戏处于中间状态（更新弹窗、公告、条款）
  2. App 启动后的标题画面/加载画面未被任务覆盖
  3. 游戏内新活动页面 / UI 改版
- **排查路径**：提取第一次 OCR 结果判断具体页面 → 去任务源码看页面规则是否漏覆盖

### 前置任务失败
- **含义**：当前任务的前置 hook（如 claim_gifts）失败，连带当前任务失败
- **排查路径**：先修复前置任务，再分析当前任务

### 账号切换失败
- **含义**：`switch_account` 流程未完成
- **常见根因**：账号管理弹窗未出现、XML 账号列表读取失败、Google 登录弹窗
- **排查路径**：看 XML dump 是否有账号列表

### not online / device offline
- **含义**：ADB 连接到设备时设备离线
- **常见根因**：模拟器重启中、ADB 服务异常、模拟器 crash
- **排查路径**：看时间戳附近是否有模拟器重启日志
</known_patterns>

<process>
按这个顺序做，不要跳：

1. 从 yuuko 拉取最新 `data`
2. 用 SQLite 先分组失败任务，不先读代码
3. 选代表账号、代表任务实例、代表时间段
4. 读 `data/logs/*.jsonl` 看失败 summary 和关键 TRACE/ERROR
5. 再去 `tasks/core/infra` 找对应源码
6. 写根因判断、修改建议、验证计划
7. 没有证据时明确写“证据不足”，不要猜
</process>

<sqlite_analysis>
先复制分析快照，避免 SQLite WAL 干扰：

```bash
rm -f /tmp/ptcgp_v2_analysis.db /tmp/ptcgp_v2_analysis.db-wal /tmp/ptcgp_v2_analysis.db-shm
cp data/ptcgp_v2.db /tmp/ptcgp_v2_analysis.db
cp data/ptcgp_v2.db-wal /tmp/ptcgp_v2_analysis.db-wal 2>/dev/null || true
cp data/ptcgp_v2.db-shm /tmp/ptcgp_v2_analysis.db-shm 2>/dev/null || true
```

最近失败通知：

```bash
sqlite3 -cmd '.timeout 5000' -header -column /tmp/ptcgp_v2_analysis.db "
select
  n.id,
  n.created_at,
  n.scene,
  n.title,
  replace(substr(n.content, 1, 220), char(10), ' | ') as content,
  n.related_account_id,
  n.related_task_instance_id,
  n.is_read
from notifications n
where n.scene='task_status'
  and n.content like '%状态: 失败%'
order by datetime(n.created_at) desc
limit 80;
"
```

按 task/reason 聚合：

```bash
uv run python - <<'PY'
import sqlite3,re
from collections import Counter
conn=sqlite3.connect('/tmp/ptcgp_v2_analysis.db')
conn.row_factory=sqlite3.Row
rows=conn.execute("""
select n.content, n.related_account_id, ti.task_type
from notifications n
left join task_instances ti on ti.id=n.related_task_instance_id
where n.scene='task_status' and n.content like '%状态: 失败%'
""").fetchall()
pat_task=re.compile(r'任务: ([^\n]+)')
pat_reason=re.compile(r'原因: ([^\n]+)')
counter=Counter()
for row in rows:
    task=row['task_type'] or pat_task.search(row['content']).group(1).strip()
    reason=pat_reason.search(row['content']).group(1).strip()
    counter[(task, reason)] += 1
for (task, reason), count in counter.most_common(40):
    print(f"{count:>4} | {task} | {reason}")
PY
```

任务实例失败状态：

```bash
sqlite3 -cmd '.timeout 5000' -header -column /tmp/ptcgp_v2_analysis.db "
select
  ti.id,
  ti.account_id,
  coalesce(a.remark, a.nickname, '') as account,
  ti.task_type,
  ti.status,
  replace(coalesce(ti.error_message, ''), char(10), ' | ') as error_message,
  ti.updated_at,
  ti.status_changed_at
from task_instances ti
left join accounts a on a.id=ti.account_id
where ti.status in ('failed','error','blocked')
   or ti.error_message is not null
order by datetime(ti.updated_at) desc
limit 120;
"
```

关联账号与任务样本：

```bash
sqlite3 -cmd '.timeout 5000' -header -column /tmp/ptcgp_v2_analysis.db "
select
  n.created_at,
  n.related_account_id,
  coalesce(a.remark, a.nickname, '') as account,
  n.related_task_instance_id,
  ti.task_type,
  ti.status,
  replace(coalesce(ti.error_message, ''), char(10), ' | ') as error_message
from notifications n
left join task_instances ti on ti.id=n.related_task_instance_id
left join accounts a on a.id=n.related_account_id
where n.scene='task_status'
  and n.content like '%状态: 失败%'
order by datetime(n.created_at) desc
limit 80;
"
```
</sqlite_analysis>

<jsonl_analysis>
先列出失败任务日志样本：

```bash
find data/logs -maxdepth 1 -type f -name '*.jsonl' | sort | tail -50
```

读 summary：

```bash
jq -c 'select(.event=="task_failure_summary")' data/logs/*.jsonl | tail -20
```

按 level 和 message 搜：

```bash
jq -c 'select(.event=="log" and .level=="ERROR") | {time, level, task, account, message}' data/logs/*.jsonl
```

```bash
jq -c 'select(.event=="log" and (.message | test("账号切换失败|not online|超过最大迭代次数|前置任务失败|unknown"))) | {time, level, task, account, message}' data/logs/*.jsonl
```

只看某个任务实例：

```bash
jq -c 'select(.task_instance_id==1234 or .event=="log")' data/logs/*instance-1234*.jsonl
```

只看 TRACE：

```bash
jq -c 'select(.event=="log" and .level=="TRACE") | {time, task, message}' data/logs/*.jsonl | tail -100
```

### unknown 溯源

```bash
jq -r 'select(.event=="log") | select((.level=="DEBUG" and (.message | startswith("OCR("))) or (.level=="ERROR" and (.message | test("任务失败")))) | "\(.time[11:19]) [\(.task)] \(.message)"' data/logs/xxxx_failed.jsonl
```
</jsonl_analysis>

<code_investigation>
排查顺序固定：

1. 先按通知和 `task_instances` 分组，找最高频失败模式
2. 对每个高频模式选 1 到 3 个代表账号和任务实例
3. 打开对应 `data/logs/*.jsonl`，先看 summary，再看 ERROR，最后看 TRACE
4. 按失败位置决定看哪个源码目录：
   - 页面流、按钮、识别分支：`src/ptcgp_auto_v2/tasks/`
   - 调度、状态流转、前置任务链：`src/ptcgp_auto_v2/core/`
   - 设备、OCR、ADB、通知、账号切换：`src/ptcgp_auto_v2/infra/`
5. 把“日志证据”和“源码位置”一一对应
6. 先写根因判断和修改建议，不先改代码

原则：

- 没有数据证据，不给确定性根因
- 先分组，再挑样本，不要随机翻代码
- 先看失败日志，再看源码，不要倒过来
- 修改建议必须说明影响面和验证方式
</code_investigation>

<report_template>
输出报告用这个结构：

```markdown
摘要
- 本次分析范围
- 最高优先级问题
- 建议先处理项

数据来源
- yuuko 同步时间
- 使用的数据库快照
- 使用的 JSONL 日志样本
- 是否使用 E2E 日志

失败分组
- task_type + error/reason 聚合结果
- 次数
- 影响账号范围
- 最近发生时间

代表样本
- 账号
- task_instance_id
- 失败时间
- summary 摘要

日志证据
- JSONL summary
- 关键 ERROR
- 关键 TRACE
- 证据说明

源码疑点
- 文件路径
- 函数名
- 可疑分支或状态变量
- 为什么和日志证据对应

修改建议
- 建议 1
- 建议 2
- 建议 3
- 每条建议写明收益、影响面、风险

验证计划
- 单元验证
- E2E 场景
- 生产观察点

风险
- 证据不足点
- 可能的误判点
- 还需要补的日志或数据
```
</report_template>

<safety_rules>
不要读取或输出以下内容：

- 账号 XML 原文
- `.env`、webhook、API key、token、cookie
- 任何 shared_prefs 或 auth 文件的敏感值

如必须接触敏感文件，只允许看：

- 文件是否存在
- 字段名/键名
- 条目数
- 时间戳、大小、路径、结构
</safety_rules>

<success_criteria>
完成标准：

- 已同步 yuuko 最新生产数据
- 已给出失败分组而不是零散样本
- 已把至少一个代表日志和一处源码对应起来
- 已输出修改建议报告
- 未读取或泄露敏感 XML、key、token 内容
- 在证据不足处明确标注，而不是猜测
</success_criteria>
