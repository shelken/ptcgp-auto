---
phase: quick-1-src-ptcgp-auto-v2-scripts-sync-metadata
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/ptcgp_auto_v2/scripts/sync_metadata.py
  - tests/ptcgp_auto_v2/scripts/test_sync_metadata.py
autonomous: true
requirements:
  - QUICK-SYNC-METADATA-01
must_haves:
  truths:
    - "运行同步脚本时，先展示本次将新增写入数据库的系列、卡牌、卡包信息。"
    - "用户未输入 y 时，不会执行任何数据库写入。"
    - "用户输入 y 后，才会执行 upsert/关联写入并输出写入统计。"
  artifacts:
    - path: "src/ptcgp_auto_v2/scripts/sync_metadata.py"
      provides: "先预览后确认的同步流程与写入闸门"
      contains: "confirm"
    - path: "tests/ptcgp_auto_v2/scripts/test_sync_metadata.py"
      provides: "预览清单与确认写入行为的自动化验证"
      contains: "test"
  key_links:
    - from: "src/ptcgp_auto_v2/scripts/sync_metadata.py"
      to: "ptcgp_auto_v2.db.repositories.card_repository.CardRepository"
      via: "仅在确认后调用 upsert_set/upsert_card/upsert_pack_safe/add_card_pack"
      pattern: "input\(.*y"
    - from: "src/ptcgp_auto_v2/scripts/sync_metadata.py"
      to: "远端 metadata JSON"
      via: "抓取后计算新增数据清单并打印"
      pattern: "requests\.get"
---

<objective>
为 `sync_metadata.py` 增加“预览新增数据 + 人工确认写入”能力，避免误写库。

Purpose: 在实际写入前让用户明确看到本次新增内容，并用显式 `y` 作为写入开关。
Output: 可交互确认的同步脚本 + 覆盖关键流程的自动化测试。
</objective>

<execution_context>
@/Users/shelken/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/shelken/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/ptcgp_auto_v2/scripts/sync_metadata.py
@src/ptcgp_auto_v2/db/repositories/card_repository.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 重构同步脚本为“收集变更”和“执行写入”两阶段</name>
  <files>src/ptcgp_auto_v2/scripts/sync_metadata.py</files>
  <action>将现有顺序写库逻辑拆成两个明确阶段：第一阶段仅抓取 sets/cards/extra 并计算“将新增写入”的数据集合（至少包含新增 set_code、新增 card(set+number)、新增 pack_name）；第二阶段接收第一阶段结果并执行数据库写入。新增数据判定优先复用仓储层读取能力（如 get_set_by_code/get_card_by_set_and_number/get_pack_by_name），不要在 core/ 或 infra/ 增加业务逻辑。</action>
  <verify>PYTHONPATH=src python -m py_compile src/ptcgp_auto_v2/scripts/sync_metadata.py</verify>
  <done>脚本中存在清晰的“预览数据构建函数”和“确认后写入函数”，预览阶段不产生任何写库调用。</done>
</task>

<task type="auto">
  <name>Task 2: 增加交互确认与新增数据清单输出</name>
  <files>src/ptcgp_auto_v2/scripts/sync_metadata.py</files>
  <action>在执行写入前输出新增清单（建议分组打印：新增系列、新增卡牌、新增卡包，并附数量及最多若干条示例）。随后提示用户输入确认文案（仅当输入值标准化后等于 y 时继续），其他输入统一视为取消并安全退出（退出码 0，日志明确“已取消，未写入数据库”）。保持原有网络拉取和异常处理语义，避免改变非本次需求的行为。</action>
  <verify>使用 stdin 管道做两次本地验证：`printf 'n\n' | PYTHONPATH=src python src/ptcgp_auto_v2/scripts/sync_metadata.py` 与 `printf 'y\n' | PYTHONPATH=src python src/ptcgp_auto_v2/scripts/sync_metadata.py`，前者日志显示取消且无写入统计，后者执行写入并输出统计。</verify>
  <done>用户可在终端先看到本次新增数据，再通过输入 y 触发写入；非 y 输入不会写入数据库。</done>
</task>

<task type="auto">
  <name>Task 3: 为预览与写入闸门补充自动化测试</name>
  <files>tests/ptcgp_auto_v2/scripts/test_sync_metadata.py</files>
  <action>新增脚本级测试，使用 mock/stub 隔离远端请求与数据库仓储，至少覆盖：1) 存在新增数据时会输出对应清单；2) 输入非 y 时不调用任何写库方法；3) 输入 y 时按预期调用 upsert_set/upsert_card/pack 相关方法。测试中固定输入输出，避免依赖真实网络和真实数据库。</action>
  <verify>PYTHONPATH=src pytest tests/ptcgp_auto_v2/scripts/test_sync_metadata.py -q</verify>
  <done>测试稳定通过，且能在回归时阻止“未确认即写入”或“清单缺失”的问题。</done>
</task>

</tasks>

<verification>
执行 `PYTHONPATH=src pytest tests/ptcgp_auto_v2/scripts/test_sync_metadata.py -q`；并手工运行一次 `printf 'n\n' | ...sync_metadata.py` 与一次 `printf 'y\n' | ...sync_metadata.py`，确认交互闸门行为与日志符合预期。</verification>

<success_criteria>
1) 同步脚本在写库前可见新增数据清单；2) 仅输入 y 时发生写库；3) 自动化测试覆盖并通过。</success_criteria>

<output>
After completion, create `.planning/quick/1-src-ptcgp-auto-v2-scripts-sync-metadata-/1-SUMMARY.md`
</output>
