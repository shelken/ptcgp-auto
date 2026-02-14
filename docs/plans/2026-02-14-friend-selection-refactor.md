# 好友选择流程重构计划

> **工作区**：`.worktrees/exchange-cards`
> **基准分支**：`exchange-cards`
> 
> **用户原始诉求**：
> 1. 统一 send_card_daily 和 exchange_cards 的好友选择流程
> 2. 缩减重复代码，保持代码简洁优雅
> 3. 修复 exchange_cards 点击 plus 后提前退出的问题

---

## 一、问题背景

### 1.1 当前问题

exchange_cards 点击 plus 后，详情页还没加载出来就匹配到 `btn_close` 并退出：

```
探测第 1/4 个 plus
OCR: "Shell 已被授予超级用户权限"  ← 详情页还没加载出来
[匹配] btn_close  ← 错误匹配到关闭按钮
点击匹配模板: btn_close  ← 提前退出
```

**根因**：缺少等待机制，send_card_daily 用"吞掉其他页面匹配"方式解决，但 exchange_cards 没有。

### 1.2 代码重复

| 模块 | send_card_daily.py | exchange_cards.py |
|------|-------------------|-------------------|
| 状态管理 | 扁平化实例属性（~20个） | dataclass 包装（_ctx） |
| `_handle_choose_friend` | 50 行 | 32 行 |
| `_handle_friend_profile` | 42 行 | 64 行 |
| `_continue_find_target_in_friend_list` | 30 行 | 18 行 |
| `_is_action_done` / `_mark_action_done` | 完全相同 | 完全相同 |

---

## 二、设计决策

### 2.1 等待机制

**方案选择**：主动循环等待（方案 C1）

**流程**：
```
点击 plus → 主动循环等待 profile 页面出现 → 直接处理 profile → 返回
```

**优点**：
- 不依赖"吞掉其他页面匹配"的隐式机制
- 逻辑更直接，状态更简单
- 移除 `friend_plus_clicked` 标记

### 2.2 状态管理

**统一使用 `FriendSelectionFlow` dataclass**：

```python
@dataclass
class FriendSelectionFlow:
    # 列表滑动状态
    scroll_rounds: int = 0
    stable_rounds: int = 0
    last_signature: Optional[str] = None
    
    # 详情页读取状态
    profile_read_rounds: int = 0
    
    # 行锚点与失败记录
    verified_row_anchor_y: Optional[int] = None
    failed_rows: set[int] = field(default_factory=set)
    
    # 探测模式状态
    probe_boxes: list = field(default_factory=list)
    probe_index: int = 0
    
    # 验证结果
    friend_verified: bool = False
```

### 2.3 锚点定位

**两边统一使用锚点方式**：
1. 点击 plus 时记录 `verified_row_anchor_y`
2. 验证成功后用锚点 + `find_send_box_near_anchor` 定位同一行的发送/交换按钮

### 2.4 failed_rows 机制

**保留**，用于有 nickname 模式的同名好友场景：

**场景**：好友列表有多个同名好友
1. 点击第一个同名好友的 plus
2. 验证失败（friend_id 不匹配）
3. 记录这个行的 Y 坐标到 `failed_rows`
4. 下次找 plus 时跳过已失败的行

**探测模式不需要 `failed_rows`**：纯遍历，没有 nickname 概念。

### 2.5 探测模式

**两边统一支持**：

**有 nickname 模式**：
- 用 nickname 定位 plus
- 用 `failed_rows` 跳过已失败的同名好友

**无 nickname 模式（探测模式）**：
- 从上到下遍历所有 plus
- 验证成功后提取 nickname 并持久化

### 2.6 nickname 提取持久化

**两边统一**：验证成功时提取 nickname 并持久化到 `AccountFriendship`。

### 2.7 失败处理

**回调模式**：公共方法接受失败回调，由调用方决定如何处理。

---

## 三、重构任务

### Task 1: 新建 `tasks/utils/friend_selection_flow.py`

包含：
- `FriendSelectionFlow` - 状态 dataclass
- `FriendSelectionHelper` - 辅助类，封装公共流程

**核心方法**：

```python
class FriendSelectionHelper:
    def tap_plus_and_wait_profile(self, plus_box) -> ActionResult:
        """点击 plus 并主动等待 profile 页面，直接处理。"""
    
    def handle_profile_verification(
        self,
        ocr_results: list[dict],
        target_friend_id: str,
        on_success: Callable,  # 验证成功回调
        on_nickname_found: Callable,  # 发现 nickname 回调
    ) -> ActionResult:
        """处理详情页验证。"""
    
    def find_plus_for_nickname(
        self,
        ocr_results: list[dict],
        target_nickname: str,
    ) -> Optional[tuple]:
        """按 nickname 找 plus（过滤 failed_rows）。"""
    
    def find_send_box_by_anchor(
        self,
        ocr_results: list[dict],
        send_text_patterns: list[str],
    ) -> Optional[tuple]:
        """按锚点找发送/交换按钮。"""
    
    def scroll_or_fail(
        self,
        signature: str,
        on_exhausted: Callable[[str], ActionResult],
    ) -> ActionResult:
        """滑动或失败回调。"""
    
    def get_next_probe_box(self) -> Optional[tuple]:
        """获取下一个探测用的 plus box。"""
```

### Task 2: 改造 `send_card_daily.py`

1. 引入 `FriendSelectionFlow` 和 `FriendSelectionHelper`
2. 删除重复的实例属性
3. 使用 Helper 处理公共流程
4. 保留送卡特有逻辑（record 状态更新等）

### Task 3: 改造 `exchange_cards.py`

1. 合并 `ExchangeFlowState` 到 `FriendSelectionFlow`
2. 使用 Helper 处理公共流程
3. 保留交换特有逻辑（request 状态更新等）

---

## 四、进度跟踪

| Task | 文件 | 状态 |
|------|------|------|
| 1 | `tasks/utils/friend_selection_flow.py` (新建) | [x] 已完成 |
| 2 | `tasks/send_card_daily.py` (改造) | [x] 已完成 |
| 3 | `tasks/exchange_cards.py` (改造) | [x] 已完成 |
| 4 | 测试验证 | [ ] 待验证 |

---

## 五、风险点

1. **改动范围大** - 需要仔细测试两个任务
2. **回滚方案** - 提交前确保可回退
