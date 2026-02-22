# Testing Patterns

**Analysis Date:** 2026-02-23

## Test Framework

**Runner:**
- pytest
- 配置：无独立配置文件，使用 `conftest.py`

**Assertion Library:**
- pytest 原生断言：`assert result.success is True`
- 类型转换：`from typing import cast`, `cast(HTMLResponse, response)`

**Run Commands:**
```bash
pytest                                         # 运行所有测试
pytest src/ptcgp_auto_v2/tests/                # 运行 v2 核心测试
pytest src/ptcgp_auto_v2/web/tests/            # 运行 Web 模块测试
pytest -v                                      # 详细输出
pytest -k "test_name"                          # 按名称筛选
```

## Test File Organization

**Location:**
- v2 核心测试：`src/ptcgp_auto_v2/tests/`（核心、infra、tasks、services 等）
- Web 模块测试：`src/ptcgp_auto_v2/web/tests/`（Web 专属：routers、queries、services）

**命名:**
- 测试文件：`test_*.py`
- 测试函数：`test_` 前缀 + 描述性名称
```python
def test_build_daily_gift_context_merges_bidirectional_pair(session: Session):
    """双向稳定关系应合并为一张配对卡片。"""
```

**Structure:**
```
src/ptcgp_auto_v2/tests/                # v2 核心测试目录
├── conftest.py                         # 公共 fixture
├── fake_adb.py                         # ADB 替身
├── test_integration.py                 # 集成测试
├── infra/                              # 基础设施测试
│   ├── test_yolo_recognition.py
│   └── test_notifier.py
├── tasks/                              # 任务测试
│   ├── test_task_registry.py
│   ├── test_collect_account_cards_task.py
│   ├── test_exchange_cards_task.py
│   └── utils/                          # 任务工具测试
│       ├── test_pack_result_mapper.py
│       └── test_high_rarity_saver.py
├── core/                               # 核心模块测试
├── services/                           # 服务层测试
├── hooks/                              # Hook 测试
├── db/                                 # 数据库测试
└── config/                             # 配置测试

src/ptcgp_auto_v2/web/tests/            # Web 模块测试
├── conftest.py                         # Web 专属 fixture
├── routers/                            # 路由层测试
│   ├── test_tasks.py
│   ├── test_management.py
│   └── ...
├── services/                           # 服务层测试
│   ├── test_notification_service.py
│   └── ...
├── queries/                            # 查询层测试
│   ├── test_friendship_queries.py
│   └── ...
└── templates/                          # 模板测试
    └── test_data_table_toolbar_layout_macro.py
```

## Test Structure

**Suite Organization:**
```python
def test_build_daily_gift_context_merges_bidirectional_pair(session: Session):
    """双向稳定关系应合并为一张配对卡片。"""
    # 1. 准备数据
    account_a = Account(game_id="gift_service_acc_1", friend_id="3000000000000001")
    account_b = Account(game_id="gift_service_acc_2", friend_id="3000000000000002")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    # 2. 执行操作
    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-11",
    )

    # 3. 断言结果
    assert len(context["pair_cards"]) == 1
    assert context["pair_anomalies"] == []
```

**Patterns:**
- **AAA 模式**：Arrange（准备）→ Act（执行）→ Assert（断言）
- **中文文档字符串**：描述测试意图
- **单一断言关注点**：每个测试验证一个行为

## Mocking

**Framework:** pytest-mock (`monkeypatch` fixture)

**Patterns:**
```python
# 替换模块函数
monkeypatch.setattr(init_account, "tap_text_exact", _fake_tap_text_exact)

# 替换类方法
monkeypatch.setattr(router, "TaskRegistry", SimpleNamespace(all_types=lambda: ["open_pack"]))

# 替换仓储层引擎（强制内存库）
monkeypatch.setattr("ptcgp_auto_v2.db.engine.get_engine", lambda: engine)
```

**替换模板引擎:**
```python
def _patch_templates(monkeypatch):
    """替换模板引擎，避免依赖真实模板渲染。"""
    class _FakeTemplates:
        def TemplateResponse(self, name, context):
            return HTMLResponse(content=f"tpl:{name}")

    monkeypatch.setattr(router, "get_templates", lambda: _FakeTemplates())
```

**替换请求表单:**
```python
async def _fake_form():
    return SimpleNamespace(
        getlist=lambda key: {"status": ["completed"]}.get(key, []),
        get=lambda key, default=None: {"account_id": "1"}.get(key, default),
    )

request = _build_request("POST")
request.form = _fake_form
```

**What to Mock:**
- 外部依赖（数据库、HTTP 请求、文件系统）
- 模板渲染（避免依赖真实模板）
- 时间相关函数（控制测试时间）

**What NOT to Mock:**
- 纯逻辑函数
- 数据模型
- 简单的数据转换

## Fixtures and Factories

**Test Data:**
```python
# 使用模型直接创建
account_a = Account(game_id="acc_001", friend_id="3000000000000001")
session.add(account_a)
session.commit()
session.refresh(account_a)

# 使用最小化替身
class _DummyAdb:
    """最小化 ADB 替身，仅用于单元测试。"""
    def center_x(self) -> int:
        return 540
    def scaled_y(self, value: int) -> int:
        return value
```

**Location:**
- 公共 fixture 在 `src/ptcgp_auto_v2/tests/conftest.py`
- Web 专属 fixture 在 `src/ptcgp_auto_v2/web/tests/conftest.py`

**核心 Fixture:**
```python
# src/ptcgp_auto_v2/tests/conftest.py
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

# src/ptcgp_auto_v2/web/tests/conftest.py
@pytest.fixture(name="memory_engine", autouse=True)
def memory_engine_fixture(monkeypatch):
    """所有 web 测试默认强制使用内存数据库引擎。"""
    engine = _create_in_memory_engine()
    _patch_repository_engines_to_memory(monkeypatch, engine)
    return engine
```

## Coverage

**Requirements:** 无强制覆盖率目标

**View Coverage:**
```bash
pytest --cov=src/ptcgp_auto_v2 --cov-report=html
open htmlcov/index.html
```

## Test Types

**Unit Tests:**
- 范围：单个函数/方法的行为
- 隔离：使用 mock 隔离外部依赖
- 示例：`src/ptcgp_auto_v2/tests/tasks/` 中的任务测试

```python
def test_handle_page_should_not_complete_on_home_without_favorite_card_marker():
    """未完成"喜欢卡牌"阶段时，进入主页不应直接判定初始化完成。"""
    task = InitAccountTask(adb=_DummyAdb(), recognizer=None, page_detector=object())
    result = task.handle_page("game_home_main", {"ocr_results": []})
    assert result.success is True
    assert task._phase != InitAccountPhase.COMPLETED
```

**Integration Tests:**
- 范围：多模块协作（如 Service + Repository）
- 隔离：使用内存数据库，但保留真实模型
- 示例：`src/ptcgp_auto_v2/tests/test_integration.py` 和服务层测试

```python
def test_build_daily_gift_context_merges_bidirectional_pair(session: Session):
    """双向稳定关系应合并为一张配对卡片。"""
    # 使用真实模型和 session
    context = build_daily_gift_context(session=session, lang="zh_CN", biz_date_local="2026-02-11")
    assert len(context["pair_cards"]) == 1
```

**E2E Tests:**
- 未使用
- 自动化任务测试通过 `--debug` 模式手动验证

## Common Patterns

**Async Testing:**
```python
# 使用 asyncio.run 执行异步函数
response = asyncio.run(
    router.reset_completed_tasks(request=request, lang="zh_CN", session=object())
)
```

**Error Testing:**
```python
# 测试边界条件
def test_build_daily_gift_context_normalizes_invalid_biz_date(session: Session):
    """非法业务日期应自动回退到当天。"""
    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="invalid-date",
    )
    assert len(context["selected_biz_date_local"]) == 10
```

**状态追踪测试:**
```python
# 使用 dict 追踪调用
called = {"country_btn": 0}

def _fake_tap_text_exact(adb, ocr, patterns, wait=1.0):
    if patterns == get_text_patterns("init_country_btn"):
        called["country_btn"] += 1
        return ActionResult.ok(wait=wait)
    return None

monkeypatch.setattr(init_account, "tap_text_exact", _fake_tap_text_exact)
# ...执行测试...
assert called["country_btn"] == 1
```

**HTTP Response 测试:**
```python
html_response = cast(HTMLResponse, response)
assert html_response.status_code == 200
trigger = json.loads(response.headers["HX-Trigger"])
assert trigger["showToast"]["message"] == "已重置 3 个任务"
```

## Test Directory Rules (Enforced)

**v2 测试目录结构:**
```
src/ptcgp_auto_v2/
├── tests/                          # 核心测试目录
│   ├── infra/                      # 基础设施测试
│   ├── tasks/                      # 任务测试
│   │   └── utils/                  # 任务工具测试
│   ├── core/                       # 核心模块测试
│   ├── services/                   # 服务层测试
│   ├── hooks/                      # Hook 测试
│   └── db/                         # 数据库测试
└── web/
    └── tests/                      # Web 专属测试
        ├── routers/                # 路由层测试
        ├── services/               # Web 服务测试
        ├── queries/                # 查询层测试
        └── templates/              # 模板测试
```

**映射规则:**
```
src/ptcgp_auto_v2/infra/*.py → tests/infra/test_*.py
src/ptcgp_auto_v2/tasks/*.py → tests/tasks/test_*.py
src/ptcgp_auto_v2/web/routers/*.py → web/tests/routers/test_*.py
src/ptcgp_auto_v2/web/services/*.py → web/tests/services/test_*.py
src/ptcgp_auto_v2/web/queries/*.py → web/tests/queries/test_*.py
```

**测试必须使用内存数据库:**
```python
# 禁止触达真实数据库
engine = create_engine("sqlite:///:memory:")
```

**测试禁止发起真实外部请求:**
```python
# 使用 monkeypatch 替换 HTTP 调用
monkeypatch.setattr(module, "http_post", fake_http_post)
```

---

*Testing analysis: 2026-02-23*
