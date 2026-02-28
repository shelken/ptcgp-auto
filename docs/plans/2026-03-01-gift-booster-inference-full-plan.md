# Gift Booster Inference Full Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在统一开包基类上实现“子包获取/判断”两阶段机制（滑动页模板识别优先，结果页卡牌反推兜底），并在开包扫描中排除 PROMO 干扰但保留普通系列缺失 Hash 下载能力。

**Architecture:** 只增强既有链路，不另起炉灶：保留 `PackOpeningTaskBase` 的页面处理、识别、落库主流程，在既有节点插入子包推断能力。第一阶段复用 `packs_auto + TemplateMatcher + PageDetector`，第二阶段复用 `DetectedCard + CardPack` 关系推断子包。所有动态模板与推断上下文均按“单次开包会话”生命周期管理并清理。

**Tech Stack:** Python 3.12, SQLModel/SQLite, pytest, ruff, 现有任务框架（Task/TaskRegistry/PageDetector/TemplateMatcher/YoloCardRecognizer/CardHashManager）。

---

## 用户原话（从指定起点开始）+ 前因后果说明

### 阶段 A：需求起点（你要求保留原话）

**前因后果说明：** 你明确要求新增“子包判断机制”，并指定两阶段策略与优先级。

> 需要一个机制来获取或者说判断子包。
>
> 两个阶段，首先是开包的时候，在「从左往右滑动」的页面，如果没有子包，那么此时尝试识别子包并回填，你需
>
> 你需要packs_auto配置加载所有子包，然后来识别当前可能的子包是哪个，需要在
> 从左往右滑动的页面进行识别，需要测试对应的缩放比例是多少。
>
> 如果识别到了，就按照这个回填。当前的pack。记住识别完成一次之后需要清理本次上下文（例如所有子包模板/和target pack context）

### 阶段 B：第二阶段反推规则

**前因后果说明：** 你定义了卡牌反推的判定细则，包含系列占比阈值、单子包直判、多子包唯一证据判定。

> 如果到扫描卡页面（开包结果页面）还是发现没有子包，此时根据识别出来的卡牌来判断当前包是哪个包。
> 我们默认只要超过一半的卡牌属于同一个系列就按照那个卡包来。
> 首先这里有个规则：如果某个系列只有一个子包那么默认使用那个子包。
> 如果某个系列多个子包，那么我们根据 CardPack 表的关联关系来判断，
> 一般情况下有些卡牌会被分配到特定子包，而不是所有子包都存在，因此，我们利用这个。对所有识别到的卡牌的关联子包关系来判断，当某张卡在这个系列的多个子包出现，我们忽略这张卡，当某个卡仅出现在某个子包下，说明，这个子包是肯定可以确定的。通过这个name，去找对应的Pack。
>
> 上面两个都是在子包没有的前提下的反推决策
> 都加上，以模板识别为第一轮，第一轮没有就使用第二轮的卡牌反推

### 阶段 C：PROMO 约束

**前因后果说明：** 你强调开包场景不应被 promo 干扰，但普通系列下载能力必须保留。

> 另外，开包扫卡的时候，我希望能够有个操作排除promo卡的加载，不然每次都会因为部分promo不存在而进行自动下载，我希望能在扫卡的时候能够让传参去抑制自动下载图片的操作。因为开包这个流程一般不可能也不会有promo的卡包出现。
>
> 下载是必须的。因为你可能遇到新系列但是数据库没有hash。所有我们应该能够控制抑制promo的情况，因为目前大部分情况下有些promo卡可能确实，但是其他的我会尽量确保都有。
> 而且为什么抑制promo，因为开包流程是不可能有promo包这种出现的，目前的开包流程只可能出现正常的a/b系列的包。
>
> 你直接检查数据库，数据库都有

**补充约束（来自上述对话）：**
- 不是“禁下载”，而是“开包链路排除 promo 干扰”。
- 必须保证普通系列（尤其新系列）缺失 Hash 时仍能自动下载。
- promo 过滤同时应用于：
  1) 第一阶段模板候选加载/匹配
  2) 第二阶段卡牌反推输入

### 阶段 D：模板加载/清理约束

**前因后果说明：** 你确认现状是按特定名字加载模板，并要求新增“批量加载 + 卸载，避免常驻”。

> 等等，目前是怎么载入相关packs auto的？通过特定名字是吗？
>
> 那是的，这个也是同样要有排除promo的机制，然后让其能够批量加载所有的子包pack模板。
> 对了，这个也一样要有卸载操作，不要让其常驻内存

### 阶段 E：实现原则（复用优先）

**前因后果说明：** 你要求“增强复用能力”为主，不接受重复并行实现。

> 你听好了，本次所有功能的新增，你必须给我完全复用原先的方法和逻辑为主。
> 主要通过增强的方式来增大代码复用能力，而不是重新写一堆重复的逻辑。

---

## 设计决策（已收敛）

1. **主流程不重建**：保留 `PackOpeningTaskBase` 现有流程，只在既有步骤中增加推断阶段处理。
2. **两阶段策略固定**：
   - 第一阶段：`pack_opening_swipe` 页面模板识别。
   - 第二阶段：`pack_opening_result` 页面卡牌反推。
3. **结果写入规则固定**：
   - 可唯一确定子包：写 `pack_code + pack_name`。
   - 仅能确定系列：写 `pack_code=系列, pack_name=None`。
4. **PROMO 策略固定**：开包扫描排除 promo，但普通系列下载能力保留。
5. **内存策略固定**：动态加载模板和推断上下文在单次开包结束后清理。

---

## 执行进度追踪

> **状态**: ✅ 已完成  
> **最后更新**: 2026-03-01

### 已完成 ✅

- [x] **Task 1**: 仓储层补齐推断所需查询能力
  - `get_pack_names_by_set(exclude_promo=True)` 已实现
  - `get_card_pack_names_batch(card_ids, exclude_promo=True)` 已实现
  - 测试: `test_card_repository.py` 3个测试通过

- [x] **Task 2**: 模板匹配器新增批量卸载能力
  - `unload_templates(template_names)` 已实现
  - 测试: `test_template_matcher.py` 4个测试通过

- [x] **Task 3**: 新增可复用子包推断工具
  - `booster_inference.py` 模块已创建
  - `infer_pack_by_templates()` 已实现（模板优先）
  - `infer_pack_by_cards()` 已实现（卡牌兜底）
  - 测试: `test_booster_inference.py` 9个测试通过

- [x] **Task 4-7**: PackOpeningTaskBase 核心增强
  - `_resolve_scan_set_code()` 优先级已修正: `fixed > explicit > inferred > None`
  - `_try_infer_pack_on_swipe()` 已实现（滑动页模板推断）
  - `_infer_pack_by_cards()` 已实现（结果页卡牌反推）
  - 模板名规范化: 使用 `normalize_name_str(pack.name)`
  - 会话清理: `finally` 块确保无论成败都清理
  - `finalize_pack_session()` 公共方法已添加

- [x] **Task 6**: 开包扫描 PROMO 排除
  - `yolo_card_recognizer.scan(exclude_promo=True)` 已实现
  - `card_hash_manager.ensure_series_ready(exclude_promo=True)` 已实现
  - `card_hash_manager.load_all_hashes(exclude_promo=True)` 已实现
  - 测试: `test_yolo_card_recognizer.py`, `test_card_hash_manager.py` 已创建

- [x] **Task 8**: 三任务接入
  - open_pack/claim_gifts/init_account 已继承 PackOpeningTaskBase
  - open_pack 显式目标上下文优先于推断
  - claim_gifts/init_account 使用推断上下文兜底

- [x] **Task 9**: Web records 展示回归
  - 服务层已兼容 `pack_name=None`
  - 测试: `test_record_service.py` 已更新

- [x] **Task 10**: 文档同步
  - `AGENTS.md` 已更新架构图和调试说明
  - `src/ptcgp_auto_v2/tasks/AGENTS.md` 已更新子包推断规范
  - `README.md` 已添加功能说明
  - 本计划文档已回填进度

### 验收结果 ✅

**聚合回归测试**: 28 个测试全部通过
- Repository 层: 3 passed
- Infra 层: 9 passed (template_matcher 4 + card_hash_manager 3 + yolo_recognizer 2)
- Utils 层: 9 passed
- Task 层: 5 passed
- Web 层: 2 passed

**关键修复验证**:
- ✅ set_code 优先级: fixed > explicit > inferred > None
- ✅ 模板名规范化: 使用 normalize_name_str()
- ✅ 会话清理: finally 块确保调用
- ✅ PROMO 排除: exclude_promo 参数正常工作
- ✅ pack_name=None: Web 展示层兼容

## 完整任务计划（每个任务给出完整逻辑）

### Task 1: 仓储层补齐推断所需查询能力（系列子包 + 卡牌子包关系）

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/card_repository.py`
- Create/Modify: `src/ptcgp_auto_v2/tests/db/repositories/test_card_repository.py`

**逻辑与原因（完整）**
- 逻辑：先在仓储层补齐两类基础数据读取能力：`系列 -> 子包列表`、`card_id -> 子包列表` 批量映射。
- 原因：第二阶段卡牌反推依赖 `CardPack` 关系，若每张卡单查会导致 N+1 查询和流程抖动；仓储先补齐后，任务层才能只做编排而不掺 SQL 细节。
- 约束：`exclude_promo=True` 只在开包推断链路使用，其他调用默认不变。

**Step 1: Write the failing test**

```python
def test_get_pack_names_by_set_excludes_promo_when_requested(session):
    repo = CardRepository()
    packs = repo.get_pack_names_by_set("A1", exclude_promo=True)
    assert all(not name.upper().startswith("PROMO") for name in packs)


def test_get_card_pack_names_batch_returns_mapping(session):
    repo = CardRepository()
    mapping = repo.get_card_pack_names_batch([1001, 1002])
    assert isinstance(mapping, dict)
    assert 1001 in mapping
    assert isinstance(mapping[1001], list)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/db/repositories/test_card_repository.py -q`
Expected: FAIL（方法不存在或行为不符）

**Step 3: Write minimal implementation**

```python
def get_pack_names_by_set(self, set_code: str, exclude_promo: bool = False) -> list[str]:
    """按系列读取子包名；exclude_promo=True 时过滤 PROMO 前缀包名。"""
    # SELECT DISTINCT pack_name FROM card_packs JOIN cards ON card_id
    # exclude_promo=True 时过滤 pack_name LIKE 'PROMO%'


def get_card_pack_names_batch(self, card_ids: list[int]) -> dict[int, list[str]]:
    """批量返回 card_id -> [pack_name, ...]。"""
    # 一次查询返回 (card_id, pack_name) 列表，再在 Python 侧聚合
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/db/repositories/card_repository.py src/ptcgp_auto_v2/tests/db/repositories/test_card_repository.py
git commit -m "feat(db): add booster inference repository queries" -m "补齐子包推断所需仓储能力：系列子包读取与卡牌子包关系批量查询。"
```

### Task 2: 模板匹配器新增批量卸载能力（避免常驻内存）

**Files:**
- Modify: `src/ptcgp_auto_v2/infra/template.py`
- Create/Modify: `src/ptcgp_auto_v2/tests/infra/test_template_matcher.py`

**逻辑与原因（完整）**
- 逻辑：在现有 `TemplateMatcher` 上新增 `unload_templates()`，仅移除本次动态加载模板，不影响核心模板。
- 原因：你要求“批量加载所有子包模板”后不能常驻内存；不卸载会持续放大模板缓存和匹配代价。
- 约束：卸载必须同时同步 `_loaded_pack_templates`，避免状态漂移。

**Step 1: Write the failing test**

```python
def test_unload_templates_removes_loaded_pack_templates(template_matcher):
    template_matcher.templates["packs_auto/Mewtwo"] = object()
    template_matcher.templates["packs_auto/Charizard"] = object()
    removed = template_matcher.unload_templates([
        "packs_auto/Mewtwo",
        "packs_auto/Charizard",
    ])
    assert removed == 2
    assert "packs_auto/Mewtwo" not in template_matcher.templates
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/infra/test_template_matcher.py -q`
Expected: FAIL（接口不存在）

**Step 3: Write minimal implementation**

```python
def unload_templates(self, template_names: list[str]) -> int:
    removed = 0
    for name in template_names:
        normalized = self._normalize_name(name)
        if normalized in self.templates:
            del self.templates[normalized]
            removed += 1
    self._loaded_pack_templates = [
        n for n in self._loaded_pack_templates if n not in set(map(self._normalize_name, template_names))
    ]
    return removed
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/infra/template.py src/ptcgp_auto_v2/tests/infra/test_template_matcher.py
git commit -m "feat(infra): support dynamic template unloading" -m "新增模板批量卸载能力，避免本次开包动态模板常驻内存。"
```

### Task 3: 新增可复用子包推断工具（模板优先 + 卡牌兜底）

**Files:**
- Create: `src/ptcgp_auto_v2/tasks/utils/booster_inference.py`
- Create: `src/ptcgp_auto_v2/tests/tasks/utils/test_booster_inference.py`

**逻辑与原因（完整）**
- 逻辑：新增纯工具模块，提供两个函数：`infer_pack_by_templates()` 与 `infer_pack_by_cards()`。
- 原因：保持 `PackOpeningTaskBase` 只做流程编排，复杂判定规则下沉工具层，满足“复用优先，不在任务里重复堆逻辑”。
- 规则固化：模板优先；反推时先判系列占比 > 50%，再做单子包直判/多子包唯一证据判定，失败时 `pack_name=None`。

**Step 1: Write the failing test**

```python
def test_template_inference_selects_best_score_pack():
    candidates = [
        {"pack_code": "A2", "booster_name": "Mewtwo", "template": "packs_auto/Mewtwo"},
        {"pack_code": "A2", "booster_name": "Charizard", "template": "packs_auto/Charizard"},
    ]

    def matcher(name: str):
        return {"score": 0.72 if name.endswith("Mewtwo") else 0.61}

    result = infer_pack_by_templates(candidate_templates=candidates, matcher_fn=matcher, threshold=0.65)
    assert result["pack_code"] == "A2"
    assert result["booster_name"] == "Mewtwo"


def test_card_fallback_majority_set_single_pack():
    detected_rows = [{"set_code": "A1", "card_id": 1}, {"set_code": "A1", "card_id": 2}, {"set_code": "A2", "card_id": 3}]
    pack_names_by_set = {"A1": ["Mewtwo"], "A2": ["Charizard", "Pikachu"]}
    result = infer_pack_by_cards(
        detected_rows=detected_rows,
        pack_names_by_set=pack_names_by_set,
        card_pack_mapping={1: ["Mewtwo"], 2: ["Mewtwo"], 3: ["Charizard"]},
    )
    assert result == {"pack_code": "A1", "booster_name": "Mewtwo", "source": "cards"}


def test_card_fallback_majority_set_multi_pack_unique_evidence():
    detected_rows = [{"set_code": "A2", "card_id": 10}, {"set_code": "A2", "card_id": 11}, {"set_code": "A2", "card_id": 12}]
    pack_names_by_set = {"A2": ["Mewtwo", "Charizard"]}
    card_pack_mapping = {10: ["Mewtwo"], 11: ["Mewtwo", "Charizard"], 12: ["Mewtwo"]}
    result = infer_pack_by_cards(detected_rows=detected_rows, pack_names_by_set=pack_names_by_set, card_pack_mapping=card_pack_mapping)
    assert result["pack_code"] == "A2"
    assert result["booster_name"] == "Mewtwo"


def test_card_fallback_ambiguous_pack_name_none():
    detected_rows = [{"set_code": "A2", "card_id": 20}, {"set_code": "A2", "card_id": 21}, {"set_code": "A3", "card_id": 22}]
    pack_names_by_set = {"A2": ["Mewtwo", "Charizard"]}
    card_pack_mapping = {20: ["Mewtwo", "Charizard"], 21: ["Mewtwo", "Charizard"]}
    result = infer_pack_by_cards(detected_rows=detected_rows, pack_names_by_set=pack_names_by_set, card_pack_mapping=card_pack_mapping)
    assert result["pack_code"] == "A2"
    assert result["booster_name"] is None
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/utils/test_booster_inference.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def infer_pack_by_templates(*, candidate_templates, matcher_fn, threshold):
    # 遍历候选模板计算分数，返回最高分且 >= threshold 的结果
    # 返回 {pack_code, booster_name, source='template', score}


def infer_pack_by_cards(*, detected_rows, pack_names_by_set, card_pack_mapping):
    # 1) 统计系列占比 > 50%
    # 2) 单子包直判
    # 3) 多子包用唯一归属卡投票
    # 4) 无法唯一则 pack_name=None
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/utils/booster_inference.py src/ptcgp_auto_v2/tests/tasks/utils/test_booster_inference.py
git commit -m "feat(tasks): add reusable two-stage booster inference utility" -m "新增模板优先、卡牌反推兜底的子包推断工具，复用既有数据结构并固化判定规则。"
```

### Task 4: 在基类插入第一阶段模板推断（滑动页）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**逻辑与原因（完整）**
- 逻辑：在现有 `_handle_opening_swipe()` 开始处新增“仅当 context 缺失时”的模板推断步骤。
- 原因：滑动页是视觉最稳定且与你规则完全一致的阶段；放在这里可最大化第一轮命中率，并避免结果页才兜底导致的信息丢失。
- 约束：单次开包会话中模板批量加载只执行一次，避免重复加载。

**Step 1: Write the failing test**

```python
def test_swipe_stage_infers_context_when_missing():
    # 进入 pack_opening_swipe 且当前无 context 时，触发模板推断并写入上下文
    task._inferred_pack_context = None
    task._try_infer_pack_on_swipe = Mock(return_value={"pack_code": "A2", "booster_name": "Mewtwo"})
    task._handle_opening_swipe({"ocr_results": []})
    assert task._inferred_pack_context["booster_name"] == "Mewtwo"


def test_swipe_stage_loads_non_promo_templates_only_once_per_pack_session():
    # 单次开包会话模板只加载一次
    task._loaded_dynamic_pack_templates = ["packs_auto/Mewtwo"]
    task._try_infer_pack_on_swipe()
    assert task._load_dynamic_pack_templates.call_count == 0
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# 新增字段
self._inferred_pack_context: dict[str, str] | None = None
self._loaded_dynamic_pack_templates: list[str] = []

# 新增方法
def _try_infer_pack_on_swipe(self):
    # 无 context 时：
    # 1. 从仓储取候选子包（排除 promo）
    # 2. 批量 load packs_auto 模板
    # 3. 在页面用多 scale 做匹配，命中则写 self._inferred_pack_context
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py
git commit -m "refactor(tasks): add swipe-stage template inference step" -m "在统一开包基类滑动页步骤中增加模板推断处理，保持主流程复用并记录会话级上下文。"
```

### Task 5: 在基类插入第二阶段卡牌反推（结果页）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`

**逻辑与原因（完整）**
- 逻辑：在 `_recognize_cards()` 保持原识别逻辑不变，追加“context 仍缺失时”执行 `infer_pack_by_cards()`。
- 原因：必须以第一阶段优先；第二阶段只做兜底，避免反推覆盖模板阶段结果。
- 约束：反推只使用当前批识别结果，不跨批次污染。

**Step 1: Write the failing test**

```python
def test_result_stage_fallback_runs_when_context_missing():
    task._inferred_pack_context = None
    task._recognize_cards()
    task._infer_pack_by_cards.assert_called_once()


def test_result_stage_writes_pack_code_only_when_pack_ambiguous():
    task._infer_pack_by_cards = Mock(return_value={"pack_code": "A2", "booster_name": None})
    task._recognize_cards()
    assert task._inferred_pack_context["pack_code"] == "A2"
    assert task._inferred_pack_context["booster_name"] is None
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def _recognize_cards(self):
    # 原有识别逻辑不变
    # 在 rows 生成后且 context 仍缺失时调用 infer_pack_by_cards 并写回上下文
    # 推断结果写入 self._inferred_pack_context
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py
git commit -m "refactor(tasks): add result-stage card fallback inference" -m "在结果页识别后新增卡牌反推子包兜底，遵循系列占比与唯一证据规则。"
```

### Task 6: 开包扫描新增 promo 排除参数（保留普通系列下载）

**Files:**
- Modify: `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py`
- Modify: `src/ptcgp_auto_v2/infra/card_hash_manager.py`
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Create/Modify: `src/ptcgp_auto_v2/tests/infra/test_yolo_card_recognizer.py`
- Create/Modify: `src/ptcgp_auto_v2/tests/infra/test_card_hash_manager.py`

**逻辑与原因（完整）**
- 逻辑：给扫描接口增加 `exclude_promo` 参数，开包路径传 `True`；Hash 加载时排除 promo 系列，但普通系列仍走缺失下载。
- 原因：你明确要求“排除 promo 干扰”同时“新系列 hash 缺失必须可下载”。
- 约束：默认参数为 `False`，不影响其他场景现有行为。

**Step 1: Write the failing test**

```python
def test_pack_scan_excludes_promo_but_keeps_normal_download():
    # exclude_promo=True 时不会加载 PROMO 系列，但普通系列缺 hash 仍会下载
    recognizer.scan(set_code=None, exclude_promo=True)
    hash_manager.load_all_hashes.assert_called_once_with(exclude_promo=True)
    hash_manager.ensure_series_ready.assert_any_call("A2", exclude_promo=True)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/infra/test_yolo_card_recognizer.py src/ptcgp_auto_v2/tests/infra/test_card_hash_manager.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# yolo_card_recognizer.scan(set_code=None, exclude_promo: bool = False)
# card_hash_manager.load_all_hashes(exclude_promo: bool = False)
# card_hash_manager.ensure_series_ready(set_code: str, exclude_promo: bool = False)
# pack_opening_task_base 在开包扫描时传 exclude_promo=True
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/infra/yolo_card_recognizer.py src/ptcgp_auto_v2/infra/card_hash_manager.py src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tests/infra/test_yolo_card_recognizer.py src/ptcgp_auto_v2/tests/infra/test_card_hash_manager.py
git commit -m "feat(infra): exclude promo in pack scan pipeline" -m "开包扫描链路支持排除PROMO干扰，同时保留普通系列缺失Hash下载能力。"
```

### Task 7: 会话结束清理（上下文 + 动态模板）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**逻辑与原因（完整）**
- 逻辑：新增 `_clear_pack_inference_session()`，统一清理推断上下文和动态模板，并在落库成功后立即调用。
- 原因：你明确要求“识别完成一次后要清理上下文和模板，不能常驻内存”。
- 约束：清理失败只打 warning，不阻塞主流程。

**Step 1: Write the failing test**

```python
def test_pack_session_cleanup_clears_context_and_unloads_templates_after_save():
    task._loaded_dynamic_pack_templates = ["packs_auto/Mewtwo"]
    task._inferred_pack_context = {"pack_code": "A2", "booster_name": "Mewtwo"}
    task._clear_pack_inference_session()
    assert task._inferred_pack_context is None
    task.template_matcher.unload_templates.assert_called_once_with(["packs_auto/Mewtwo"])
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def _clear_pack_inference_session(self):
    # unload_templates(self._loaded_dynamic_pack_templates)
    # self._loaded_dynamic_pack_templates.clear()
    # self._inferred_pack_context = None

# 在 _save_pack_record 成功后与任务结束路径调用
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py
git commit -m "fix(tasks): clean pack inference session resources" -m "开包会话结束后清理推断上下文并卸载动态模板，防止模板常驻内存。"
```

### Task 8: 三任务接入增强后的基类能力并回归

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py`

**逻辑与原因（完整）**
- 逻辑：三任务不重写开包主流程，仅通过扩展点接入推断结果读取；`open_pack` 目标上下文优先级保持不变。
- 原因：你要求“增强复用，不重复实现”。
- 约束：`claim_gifts/init_account` 无显式 target 时依赖推断；`open_pack` 有显式 target 时不被推断覆盖。

**Step 1: Write the failing test**

```python
def test_claim_gifts_record_contains_inferred_pack_code_and_nullable_pack_name():
    task._inferred_pack_context = {"pack_code": "A2", "booster_name": None}
    task._save_pack_record([{"card_name": "Card #1", "rarity": "R", "position": 1}])
    kwargs = task._pack_record_repo.create_for_account.call_args.kwargs
    assert kwargs["pack_code"] == "A2"
    assert kwargs["pack_name"] is None


def test_open_pack_existing_target_context_still_has_priority():
    task._target_pack = {"pack_code": "A1", "booster_name": "Mewtwo"}
    task._inferred_pack_context = {"pack_code": "A2", "booster_name": "Charizard"}
    assert task.get_target_pack_context()["pack_code"] == "A1"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# 子类不重写主流程，仅保持扩展点
# get_target_pack_context() 读取顺序：
# 1) 基类推断上下文
# 2) 子类原有目标上下文（如 open_pack 的 _target_pack）
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/open_pack.py src/ptcgp_auto_v2/tasks/claim_gifts.py src/ptcgp_auto_v2/tasks/init_account.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py
git commit -m "refactor(tasks): wire three tasks to enhanced pack inference" -m "open_pack/claim_gifts/init_account 在不重复实现流程的前提下接入两阶段子包推断。"
```

### Task 9: Web records 展示回归（pack_name 可空）

**Files:**
- Modify: `src/ptcgp_auto_v2/web/services/record_service.py`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/record_list.html`
- Modify/Create: `src/ptcgp_auto_v2/web/tests/services/test_record_service.py`

**逻辑与原因（完整）**
- 逻辑：服务层与模板明确支持 `pack_name=None` 展示路径，保证仅有 `pack_code` 也能稳定渲染。
- 原因：第二阶段反推在“系列确定但子包不唯一”时会写 `pack_name=None`，前端必须兼容。
- 约束：不改变已有字段协议，避免影响其他列表渲染。

**Step 1: Write the failing test**

```python
def test_record_list_renders_when_pack_name_is_none_but_pack_code_exists(session):
    context = build_records_list_context(session=session)
    assert "pack_name_display" in context["items"][0]
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/services/test_record_service.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# 服务层与模板处理 pack_name=None 容错
# 保持原有字段协议不变
```

**Step 4: Run test to verify it passes**

Run: 同 Step 2
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/services/record_service.py src/ptcgp_auto_v2/web/templates/partials/record_list.html src/ptcgp_auto_v2/web/tests/services/test_record_service.py
git commit -m "fix(web): support nullable inferred pack_name in records" -m "records 列表兼容仅有系列无子包名称的推断记录展示。"
```

### Task 10: 文档同步 + 全量验收

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `src/ptcgp_auto_v2/tasks/AGENTS.md`
- Modify: `docs/plans/2026-03-01-gift-booster-inference-full-plan.md`

**逻辑与原因（完整）**
- 逻辑：同步 README/AGENTS/tasks-AGENTS 的结构与规则说明，并执行任务+web关键回归作为交付门禁。
- 原因：这是结构级增强，必须文档对齐，避免后续开发者误用术语或流程。
- 约束：只补充规则与结构说明，不改动无关章节。

**Step 1: Write the failing test**

```python
def test_docs_include_two_stage_inference_rules():
    assert "两阶段" in read_text("README.md")
    assert "promo" in read_text("AGENTS.md")
    assert "模板卸载" in read_text("src/ptcgp_auto_v2/tasks/AGENTS.md")
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python scripts/check_docs_keyword.py --files README.md AGENTS.md src/ptcgp_auto_v2/tasks/AGENTS.md --keywords "两阶段" "promo" "模板卸载"`
Expected: FAIL（未同步前）

**Step 3: Write minimal implementation**

```markdown
- README: 增补两阶段子包推断与记录规则
- AGENTS: 增补复用优先与推断规则
- tasks/AGENTS: 增补扩展点约束与反模式
```

**Step 4: Run test to verify it passes**

Run:
- `ruff check src/ptcgp_auto_v2/tasks src/ptcgp_auto_v2/web/services/record_service.py`
- `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py src/ptcgp_auto_v2/web/tests/services/test_record_service.py -q`
Expected: 全部 PASS

**Step 5: Commit**

```bash
git add README.md AGENTS.md src/ptcgp_auto_v2/tasks/AGENTS.md docs/plans/2026-03-01-gift-booster-inference-full-plan.md src/ptcgp_auto_v2/tasks src/ptcgp_auto_v2/web/services/record_service.py src/ptcgp_auto_v2/web/tests/services/test_record_service.py
git commit -m "fix(tasks): finalize two-stage booster inference rollout" -m "完成子包推断两阶段增强、promo排除与资源清理机制，并同步文档与回归验收。"
```

---

## 执行硬约束（不可违反）

- 新增能力必须“复用原有方法和逻辑为主”，通过增强提升复用，不得平行重写主流程。
- 第一轮模板识别优先，失败后第二轮卡牌反推，顺序不得颠倒。
- 无法唯一确定子包时严格写：`pack_code=系列`, `pack_name=None`。
- 开包扫描排除 promo，但普通系列缺 hash 下载能力必须保留。
- 动态模板与推断上下文不得常驻内存，必须按开包会话清理。
- 禁止 `git add -A`，按任务文件显式 add。
