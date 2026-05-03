---
name: analyze-production-failures
description: Analyzes production failures by syncing data from yuuko, querying notifications and task tables, reading data/logs JSONL slices, correlating evidence with src/ptcgp_auto_v2/tasks, src/ptcgp_auto_v2/core, and src/ptcgp_auto_v2/infra, then producing a modification recommendation report. Use when the user mentions yuuko, production data, 通知表, 失败任务, data/logs, or 错误任务分析.
---

<objective>
从 yuuko 同步最新生产数据，分析通知表与任务状态错误，结合失败任务 JSONL 日志和源码定位问题，并输出可执行的修改建议报告。这个 skill 先做数据分析和定位，不先改代码。
</objective>

<quick_start>
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
