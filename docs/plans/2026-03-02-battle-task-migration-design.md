# v2 对战任务迁移设计文档

## 原始需求（用户原话）

> 准备将 v1 的对战逻辑迁移到v2

## 用户纠正与澄清（原话记录）

### 纠正 1：关于卡包/系列的定义

**用户原话：**
> 纠正下，目前卡包是只有模板，没有hash，只有卡牌才用到hash。然后不要考虑兜底，大概应该需要重新设计，需要重新思考原先可能不够合理的地方，所以对旧的逻辑需要严谨考虑是否复用。

**用户原话：**
> 纠正下原先的一些描述，我发现这个不是按照子包来的，而是一个系列一个系列来的，所以我重新调整下原先描述，原先说用卡包，其实都是卡包对应的系列，也就是set_code。

**要点：**
- 只有卡牌使用 hash，卡包使用模板
- 不考虑兜底逻辑
- 按系列（set_code）而非子包来处理

---

### 纠正 2：关于数据模型设计

**用户原话：**
> 这个progress设计不太好，我希望你能直接用一条记录来表示
> account_id, status, set_code, level, updated_at, progress_name
> 应该是账号1对多的关系

**要点：**
- 一条记录表示一个系列+等级的进度
- 账号与进度为 1 对多关系
- 字段：account_id, status, set_code, level, updated_at, progress_name

---

### 纠正 3：关于系列选择

**用户原话：**
> 卡包识别相关的你直接参考我在open pack中如何寻找对应卡包的方式来，不过这里稍微不同。我们要寻找系列，很简单，我们可以拿到系列有哪些子包，通过子包对应的模板，循环寻找对应模板就行了。只是选择扩充包列表页面可能需要不同的比例而已，问题不大 @src/ptcgp_auto_v2/config/constants.py 中加上新的SCALE_PACK_*比例然后引用就行。

**用户原话：**
> 纠正下，不是packs了，现在都是packs_auto相关的，具体你直接去看看 @src/ptcgp_auto_v2/tasks/pack_opening_task_base.py 里面或者 @src/ptcgp_auto_v2/tasks/open_pack.py 里面看看我们如何直接调用模板查找的。

**要点：**
- 通过子包模板循环查找来确定系列
- 参考 open_pack.py 的模板查找方式
- 新增 SCALE_BATTLE_SERIES_SELECT 比例常量
- 使用 PackImageManager 和 template_matcher

---

### 纠正 4：关于卡包识别流程

**用户原话：**
> 卡包识别流程的第三步不对，你混入了沙漏，这个跟卡包识别没关系。

**要点：**
- 卡包识别和沙漏检测是分开的
- 卡包识别：确定是什么系列/卡包
- 沙漏检测：判断是否可以进行对战（完成状态）

---

### 纠正 5：关于执行思路转变

**用户原话：**
> 原先我们都是按照完成所有的目的来点击所有系列。但是我们现在是通过停止条件来驱动我们，所以从原先的点击所有，变成根据配置来精确选择系列和难度，然后根据目前的数据库状态和进度来选择，需要转变思路。

**要点：**
- 不再遍历所有系列
- 由配置指定 set_code + level
- 停止条件驱动，而非"全部完成"驱动

---

### 纠正 6：关于停止条件

**用户原话：**
> 停止条件我认为应该有：ABCE
> C描述不对，跟开包点数没关系，原先的目标是获取沙漏。
> 停止条件还可以是：完成某个等级的所有卡包。例如完成精英等级。
> 停止条件没有默认一说，就是什么任务可能需要什么停止条件，而对战任务要做的就是开始时知道当前账号的停止条件是什么

**要点：**
- 停止条件类型：A(时间) B(次数) C(沙漏) E(无奖励)
- 新增：完成某个等级的所有卡包
- C 是沙漏数，不是开包点数
- 停止条件由配置指定，没有默认值

---

### 纠正 7：关于触发方式

**用户原话：**
> 触发：AB
> A应该是直接对某个账号下发对战任务（支持配置停止条件选择）
> B应该不叫插入，而是使用触发当前账号task instance的方式，然后跳过本次任务。
> C暂时不需要 D也暂时不需要

**要点：**
- A: Web UI 手动下发（支持配置停止条件）
- B: 其他任务通过触发 task instance 方式，跳过当前任务执行对战

---

### 纠正 8：关于教程解锁

**用户原话：**
> 教程解锁这个应该也需要并入同一个task，而不是之前的额外子循环。我觉得应该把这个作为一个完整的方法来调用。当进入对战页面发现需要进入教程模式的时候，直接进入某个方法，然后循环，直到完成所有教程。

**要点：**
- 教程解锁整合到 BattleTask 中
- 作为一个方法调用，而非独立子循环
- 检测到需要解锁时进入，完成后返回主流程

---

## 调研总结

### v1 对战架构 (`src/ptcgp_auto/`)

**核心文件：**
- `battle.py`: 开始对战、等待对战、检测自动模式
- `tutorial.py`: 新手教程解锁流程（00-06），独立子循环
- `expansion.py`: 扩充组选择，使用数字组合识别卡包
- `deck.py`: 牌组列表，检测沙漏图标
- `state_manager.py`: 本地 JSON 文件存储等级/卡包完成状态

**v1 卡包识别（需要重新设计）：**
- 原方案：OCR 识别 `左进度/总数` + `右进度/总数`，生成 `系列_左分母_右分母` 作为 pack_id
- 问题：数字识别不稳定，不同卡包可能有相同数字组合
- 新方案：使用模板名称作为标识

### v2 任务架构 (`src/ptcgp_auto_v2/`)

**核心特性：**
- `Task` 基类：目标驱动 + 页面响应模式
- 数据库持久化：账号、任务计划、任务实例
- 调度器 + 执行器：多账号、多设备、原子任务
- `ActionResult`: 统一动作结果返回

**参考实现：**
- `open_pack.py`: 模板查找、PackImageManager 使用
- `pack_opening_task_base.py`: 任务基类扩展模式

---

## 数据模型设计

### 表：`account_battle_progress`

```python
class AccountBattleProgress(SQLModel, table=True):
    """账号对战进度表

    记录每个账号在特定系列+等级下的对战进度
    账号与记录为 1 对多关系
    """
    __tablename__ = "account_battle_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)

    # 系列代码（A1, A2, B1 等）
    set_code: str

    # 难度等级（初級, 中級, 上級, 精英等）
    level: str

    # 当前进度状态（进行中的卡包模板名，如 "Charizard"）
    # 空字符串表示该系列+等级已完成
    progress_pack: str = Field(default="", description="当前卡包模板名，空表示完成")

    # 累计对战次数（用于统计）
    battle_count: int = Field(default=0)

    # 累计获得沙漏数
    hourglass_earned: int = Field(default=0)

    updated_at: datetime = Field(default_factory=datetime.now)

    # 唯一约束：一个账号在一个系列+等级下只有一条记录
    class Config:
        unique_together = [("account_id", "set_code", "level")]
```

**设计说明：**
- 由调用方指定 `set_code` + `level`，任务不自动遍历所有系列
- `progress_pack` 记录当前进行中的卡包模板名，用于中断后继续
- 完成所有卡包后，`progress_pack` 置空表示该系列+等级已完成

> 纠正：已修正。简化表结构，只记录是否完成。

### 修正后的 `account_battle_progress` 表

```python
class AccountBattleProgress(SQLModel, table=True):
    """账号对战进度表

    记录账号在特定系列+等级下的完成状态
    """
    __tablename__ = "account_battle_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    set_code: str      # 系列代码（A1, A2 等）
    level: str         # 难度等级（初級, 中級, 上級, 精英等）
    status: str        # "in_progress" / "completed"
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        unique_together = [("account_id", "set_code", "level")]
```

**说明：**
- 只记录该系列+等级是否已完成（`completed`）
- 不记录进度中的卡组、不统计对战次数/沙漏数
- 这些运行时统计由 `BattleTaskConfig` 或 `TaskInstance` 处理

### 表：`battle_task_config`

```python
class BattleTaskConfig(SQLModel, table=True):
    """对战任务配置表（用于手动下发时存储配置）"""
    __tablename__ = "battle_task_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int
    task_instance_id: int  # 关联的 task_instance

    # 停止条件配置 (JSON)
    # 停止条件本身包含目标信息，例如：
    # [{"type": "level_complete", "set_code": "A1", "level": "精英"}]
    # [{"type": "time", "value": 30}, {"type": "hourglass", "value": 3, "set_code": "A1", "level": "精英"}]
    stop_conditions: str

    created_at: datetime = Field(default_factory=datetime.now)
```

> 纠正：已修正。停止条件本身就包含目标信息（set_code + level），不需要额外的 target 字段。

---

## 系列选择设计

参考 `open_pack.py` 的模式，通过子包模板寻找系列：

```python
def _find_series_by_template(self, target_set_code: str) -> Optional[Box]:
    """
    通过子包模板查找目标系列

    Args:
        target_set_code: 目标系列代码（如 "A1", "A2"）

    Returns:
        系列按钮的点击位置，未找到返回 None
    """
    # 1. 获取该系列下的所有子包
    packs = self._card_repo.get_packs_by_set_code(target_set_code)
    if not packs:
        return None

    manager = PackImageManager()
    _, template_matcher = self.recognizer

    # 2. 循环尝试每个子包模板
    for pack in packs:
        if pack.set_code.upper().startswith("PROMO"):
            continue

        # 确保模板已加载
        if not manager.ensure_template_ready(template_matcher, pack.name):
            continue

        template_name = manager.get_template_name(pack.name)

        # 3. 使用系列选择页面比例查找
        match = template_matcher.find_with_scale(
            screenshot,
            template_name,
            scale=settings.scale_battle_series_select,  # 新增比例常量
            threshold=settings.pack_template_threshold,
        )
        if match:
            logger.info(f"找到系列 {target_set_code}，通过子包 {pack.name}")
            return match

    return None
```

> 纠正：已修正。优化为只查询一次数据库缓存结果，且只在系列选择页面使用模板匹配。

### 优化后的系列选择设计

```python
class BattleTask(Task):
    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        # 缓存该系列的所有子包模板名
        self._series_pack_names: list[str] = []

    def on_start(self):
        """预加载该系列的所有子包模板名"""
        # 只查询一次数据库
        packs = self._card_repo.get_packs_by_set_code(self._target_set_code)
        self._series_pack_names = [
            p.name for p in packs
            if not p.set_code.upper().startswith("PROMO")
        ]
        # 预加载所有模板
        manager = PackImageManager()
        _, template_matcher = self.recognizer
        for name in self._series_pack_names:
            manager.ensure_template_ready(template_matcher, name)

    def _find_series_in_screenshot(self, screenshot) -> Optional[Box]:
        """
        在当前截图中查找系列位置
        只遍历已缓存的模板名，不再查询数据库
        """
        _, template_matcher = self.recognizer
        manager = PackImageManager()

        for pack_name in self._series_pack_names:
            template_name = manager.get_template_name(pack_name)
            match = template_matcher.find_with_scale(
                screenshot,
                template_name,
                scale=settings.scale_battle_series_select,
                threshold=settings.pack_template_threshold,
            )
            if match:
                return match
        return None
```

### 需要新增的常量

在 `src/ptcgp_auto_v2/config/constants.py` 中添加：

```python
# 对战任务系列选择页面比例
SCALE_BATTLE_SERIES_SELECT = 1.15  # 待调试确定
```

> 纠正：已修正。只有系列选择页面需要模板比例。后续卡组选择页面通过沙漏图标检测，不需要模板匹配卡组。

---

## 卡包状态识别设计

> 纠正：已删除。卡包识别与沙漏检测无关，后续在卡组选择页面直接检测沙漏图标即可。

---

## 停止条件设计

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta


class StopCondition(ABC):
    """停止条件基类"""

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def check(self, task: "BattleTask") -> bool: ...


@dataclass
class TimeLimitCondition(StopCondition):
    """A: 时间限制停止条件"""
    minutes: int

    @property
    def description(self) -> str:
        return f"运行时间达到 {self.minutes} 分钟"

    def check(self, task: "BattleTask") -> bool:
        if not task._start_time:
            return False
        elapsed = datetime.now() - task._start_time
        return elapsed >= timedelta(minutes=self.minutes)


@dataclass
class BattleCountCondition(StopCondition):
    """B: 对战次数停止条件"""
    count: int

    @property
    def description(self) -> str:
        return f"完成 {self.count} 场对战"

    def check(self, task: "BattleTask") -> bool:
        return task._battle_count >= self.count


@dataclass
class HourglassCondition(StopCondition):
    """C: 沙漏获取停止条件（修正：不是开包点数）"""
    count: int

    @property
    def description(self) -> str:
        return f"获得 {self.count} 个沙漏"

    def check(self, task: "BattleTask") -> bool:
        current = task._get_current_hourglass_count()
        gained = current - task._hourglass_before
        return gained >= self.count


@dataclass
class LevelCompleteCondition(StopCondition):
    """完成某个等级的所有卡包"""
    level: str  # "精英" 或特定等级名

    @property
    def description(self) -> str:
        return f"完成 {self.level} 等级的所有卡包"

    def check(self, task: "BattleTask") -> bool:
        return task._is_current_level_complete()


@dataclass
class NoRewardCondition(StopCondition):
    """E: 无首次过关奖励停止条件（说明该卡包已刷满）"""

    @property
    def description(self) -> str:
        return "检测到无首次过关奖励"

    def check(self, task: "BattleTask") -> bool:
        return task._detect_no_first_clear_reward()
```

---

## 任务架构设计

> 纠正：已修正。仅保留框架和页面规则，先调通页面识别再添加业务逻辑。

```python
@TaskRegistry.register("battle")
class BattleTask(Task):
    """
    对战任务 - 刷经验获取沙漏
    （页面调通后再添加完整逻辑）
    """

    task_type = "battle"
    reset_type = ResetType.ONCE
    pages = []  # 待通过 debug ocr 收集页面规则后填充

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        # 页面调通后再添加业务逻辑

    def on_start(self):
        """页面调通后实现：加载停止条件和进度"""
        pass

    def is_completed(self) -> bool:
        """页面调通后实现：检查停止条件"""
        return False

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """
        页面处理 - 先仅输出当前页面
        页面调通后再添加实际处理逻辑
        """
        logger.info(f"[BattleTask] 当前页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def _handle_tutorial_unlock(self):
        """页面调通后实现：教程解锁处理"""
        pass
```

> 纠正：已简化。先调通页面识别，确认能正确识别各页面后，再逐步添加业务逻辑。

---

## 需要收集的页面信息

使用 `python debug_tool.py -a [port] --ocr` 收集以下页面的 OCR 特征：

### 对战相关页面

1. **battle_home** - 单人对战主页（选择初级/中级/上级/精英）
   - 需要文字："與人對戰" / "單人對戰" / 各等级名称

2. **tutorial_list** - 教程列表
   - 需要文字："玩法" / 沙漏图标

3. **tutorial_battle** - 教程对战中
   - 需要文字："對戰對手" / "派出手牌" / "結束回合"
   - 需要模板：手指引导、blue_circle、OK按钮

4. **level_select** - 难度选择页面
   - 需要文字："初級" / "中級" / "上級" / "精英"

5. **series_select** - 系列选择页面
   - 需要文字：各系列名称
   - 需要模板：系列按钮

6. **pack_select** - 卡包选择页面（显示各卡包和沙漏/CLEAR）
   - 需要模板：各卡包模板、沙漏图标、CLEAR标记

7. **battle_prepare** - 对战准备页面
   - 需要文字："首次過關報酬" / 自动模式开关
   - 需要模板：对战按钮

8. **in_battle** - 对战中页面
   - 需要文字："自動對戰中"

9. **battle_result** - 对战结果页面
   - 需要文字："首次過關報酬" / 沙漏数量

10. **battle_complete_popup** - 卡包完成弹窗
    - 需要文字：提示无奖励/已完成

---

## 实现计划

### Phase 1: 数据模型
- [ ] 创建 `account_battle_progress` 表
- [ ] 创建 `battle_task_config` 表
- [ ] 添加数据库迁移脚本

### Phase 2: 页面收集
- [ ] 使用 debug_tool 收集所有对战相关页面的 OCR 特征
- [ ] 确定页面识别规则
- [ ] 调试系列选择页面的模板比例

### Phase 3: 核心功能
- [ ] 实现 `BattleTask` 基础架构
- [ ] 实现系列选择（通过子包模板）
- [ ] 实现卡包状态检测（沙漏/CLEAR）
- [ ] 实现停止条件系统

### Phase 4: 教程整合
- [ ] 整合 v1 tutorial.py 逻辑
- [ ] 实现教程检测和自动处理

### Phase 5: 触发方式
- [ ] Web UI 手动下发任务
- [ ] Hook 触发机制

### Phase 6: 测试
- [ ] 单元测试
- [ ] 集成测试
- [ ] 长时间运行测试

---

## 待讨论问题

1. **页面识别细节**：需要通过 debug ocr 实际收集页面特征后才能确定
2. **模板比例**：SCALE_BATTLE_SERIES_SELECT 需要通过实际测试确定
3. **CLEAR 标记识别**：通过 OCR 文字还是模板匹配？
4. **沙漏数量获取**：对战结果页如何准确识别获得的沙漏数量？

---

*文档创建时间：2026-03-02*
*基于用户纠正后的设计*
