# 每日开包功能设计文档

> 创建时间：2026-01-16
> 状态：**Phase 1-3 基础框架已完成**

## 用户源需求

```
我们现在开始做计划，我打算增加一个功能，就是每日给所有账号进行刷两个免费的包，因为这个任务比较复杂，应该需要引
入更多复杂的架构。例如，当我python main.py --all --log-level DEBUG --daily 时，daily为新增参数，说明当前不再是
原先的主逻辑去自动对战获取奖励，而是进入新模式，自动轮换所有账号的xml文件并自动开包。

因为需要配置哪些账号开哪些包和保存账号的信息（例如id，用户名，xml信息），我们应该需要开始引入数据库文件，sqlite
或者连接远程pgsql，这个部分可以深入讨论，但是肯定是需要数据库的

xml文件的获取需要root，因此需要判断当前连接的设备是否有root，如果没有则排除掉设备。然后，进来的逻辑应该是，进来
后（复用原来获取当前已经启动的模拟器，获取所有adb端口，然后连接所有模拟器），然后连接数据库获取待开包的所有账号
信息，开始在当前已连接的adb下多线程分配所有账号。重点：在我们覆盖账号信息前，先提取当前存在的账号信息，检查是否
在数据库存在，如果不存在，我们应该先进入游戏，通过ocr获取用户的id和用户名然后提取xml进入数据库保存，通过ocr获取
用户信息的操作可以复用原来的逻辑。xml文件的结构后续需要实际获取之后看看是否可以从中提取哪些有用的结构和信息。
提取后覆盖待开包用户，退出应用之后重新进入，进到主界面，获取当前账号应该开的包，这部分根据配置来，后续打算写一
个tui来连接数据库方便用户管理配置信息。 开包后，更新数据库当前账号开包时间，切换当前模拟器分配的下一个账号。

当所有账号完成每日开包后，标注本日结束，但是不退出，需要常驻，进入定时扫描，扫描当前数据库中上次开包时间大于24h
的账号，然后重复上述开包流程。直到用户退出程序。


以上规划在codeing阶段，一定要懂得模块化设计，高内聚低耦合原则，单代码文件最多不要超过500行，能复用原来逻辑的部
分，可以提取出公共代码
```

## 1. 需求概述

### 1.1 功能目标

新增 `--daily` 模式，实现每日自动轮换所有账号开免费包的功能。

### 1.2 使用方式

```bash
python main.py --all --log-level DEBUG --daily
```

### 1.3 核心需求

1. **新模式入口**：`--daily` 参数启用每日开包模式，独立于原有的自动对战模式
2. **数据库支持**：引入数据库管理账号信息和开包状态
3. **Root 检测**：自动检测设备是否已 root，排除未 root 设备
4. **账号轮换**：多线程分配账号到已连接的模拟器
5. **账号提取**：覆盖前先提取当前账号，检查是否在数据库中
6. **OCR 用户信息**：复用现有逻辑获取用户 ID 和用户名
7. **配置化开包**：根据配置决定每个账号开哪些包
8. **定时扫描**：完成后常驻，定时扫描 >24h 未开包的账号

---

## 2. 技术架构

### 2.1 新增模块

```
src/ptcgp_auto/
├── daily/                      # 每日开包模块（新增）
│   ├── __init__.py
│   ├── runner.py               # DailyRunner 主类
│   ├── account_manager.py      # 账号管理器
│   ├── pack_opener.py          # 开包执行器
│   ├── scheduler.py            # 定时调度器
│   └── root_checker.py         # Root 检测
├── db/                         # 数据库模块（新增）
│   ├── __init__.py
│   ├── connection.py           # 数据库连接管理
│   ├── models.py               # 数据模型
│   └── repository.py           # 数据访问层
└── xml/                        # XML 账号操作（新增）
    ├── __init__.py
    ├── extractor.py            # 账号提取
    └── injector.py             # 账号注入
```

### 2.2 数据库设计

#### 选型讨论

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **SQLite** | 零配置、单文件、便携 | 并发写入受限 | 单机使用、开发阶段 |
| **PostgreSQL** | 高并发、远程访问、扩展性强 | 需要部署维护 | 多机协作、生产环境 |

**建议**：先实现 SQLite，预留 PostgreSQL 接口。

#### 数据模型

```sql
-- 账号表
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT UNIQUE NOT NULL,       -- 游戏内 ID
    username TEXT,                       -- 用户名
    xml_path TEXT,                       -- XML 文件路径
    xml_hash TEXT,                       -- XML 内容哈希（用于去重）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 开包记录表
CREATE TABLE pack_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    pack_type TEXT NOT NULL,            -- 开的包类型
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- 账号配置表
CREATE TABLE account_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    pack_preference TEXT,               -- JSON: 开包偏好配置
    enabled BOOLEAN DEFAULT TRUE,       -- 是否启用
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### 2.3 流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         每日开包模式主流程                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. 启动                                                                 │
│     ├─ 解析 --daily 参数                                                 │
│     ├─ 初始化数据库连接                                                   │
│     └─ 发现所有已启动的模拟器                                             │
│                                                                          │
│  2. 设备过滤                                                             │
│     ├─ 连接所有 ADB 设备                                                  │
│     ├─ 检测每个设备是否 root                                              │
│     └─ 排除未 root 的设备                                                 │
│                                                                          │
│  3. 账号分配                                                             │
│     ├─ 从数据库获取待开包账号（上次开包 >24h）                             │
│     └─ 多线程分配账号到可用设备                                           │
│                                                                          │
│  4. 单设备开包循环                                                        │
│     │                                                                    │
│     ├─ 4.1 提取当前账号                                                  │
│     │      ├─ 通过 ADB 提取 deviceAccount:.xml                           │
│     │      ├─ 计算 XML 哈希                                              │
│     │      └─ 检查是否在数据库中                                          │
│     │           ├─ 不存在 → 进入游戏，OCR 获取用户信息，保存到数据库        │
│     │           └─ 存在 → 继续                                           │
│     │                                                                    │
│     ├─ 4.2 注入待开包账号                                                │
│     │      ├─ 强制关闭游戏                                               │
│     │      ├─ 推送 XML 到设备                                            │
│     │      └─ 启动游戏                                                   │
│     │                                                                    │
│     ├─ 4.3 开包流程                                                      │
│     │      ├─ 等待进入主界面                                             │
│     │      ├─ 根据配置选择要开的包                                        │
│     │      ├─ 执行开包动作（复用现有 actions）                            │
│     │      └─ 更新数据库开包时间                                          │
│     │                                                                    │
│     └─ 4.4 切换下一个账号                                                │
│            └─ 重复 4.1 - 4.3                                             │
│                                                                          │
│  5. 完成后常驻                                                           │
│     ├─ 标记本轮完成                                                      │
│     └─ 定时扫描（每小时检查 >24h 未开包的账号）                            │
│           └─ 有待开包账号 → 回到步骤 3                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 模块设计

### 3.1 Root 检测模块 (`root_checker.py`)

```python
def is_rooted(device_address: str) -> bool:
    """检查设备是否已 root"""
    try:
        result = subprocess.run(
            ["adb", "-s", device_address, "shell", "su", "-c", "echo 1"],
            capture_output=True,
            text=True,
            timeout=3
        )
        return result.stdout.strip() == "1"
    except:
        return False
```

### 3.2 XML 操作模块

#### 提取 (`extractor.py`)

```python
def extract_account(adb: AdbController) -> Optional[str]:
    """提取当前设备的账号 XML"""
    # 1. adb shell su -c 'cp deviceAccount:.xml /sdcard/'
    # 2. adb pull /sdcard/deviceAccount.xml
    # 3. 返回本地路径
```

#### 注入 (`injector.py`)

```python
def inject_account(adb: AdbController, xml_path: str) -> bool:
    """注入账号 XML 到设备"""
    # 1. adb shell am force-stop jp.pokemon.pokemontcgp
    # 2. adb push xml_path /sdcard/deviceAccount.xml
    # 3. adb shell su -c 'cp /sdcard/deviceAccount.xml shared_prefs/'
    # 4. adb shell am start -n jp.pokemon.pokemontcgp/...
```

### 3.3 账号管理器 (`account_manager.py`)

```python
class AccountManager:
    def __init__(self, db: Database):
        self.db = db

    def get_pending_accounts(self, hours: int = 24) -> List[Account]:
        """获取待开包账号（上次开包超过指定小时）"""

    def register_account(self, xml_path: str, game_id: str, username: str) -> Account:
        """注册新账号"""

    def update_pack_time(self, account_id: int, pack_type: str):
        """更新开包时间"""
```

### 3.4 每日开包运行器 (`runner.py`)

```python
class DailyRunner:
    def __init__(self, db: Database, devices: List[str]):
        self.db = db
        self.devices = devices
        self.account_manager = AccountManager(db)

    def run(self):
        """主运行循环"""
        # 1. 过滤 root 设备
        # 2. 分配账号
        # 3. 多线程执行开包
        # 4. 完成后进入定时扫描
```

---

## 4. 复用现有模块

| 现有模块 | 复用部分 | 用途 |
|----------|----------|------|
| `device_discovery.py` | `discover_devices()` | 发现已启动的模拟器 |
| `adb_controller.py` | 全部 | ADB 操作 |
| `recognizer.py` | OCR、模板匹配 | 界面识别 |
| `page_detector.py` | `detect()` | 识别当前页面 |
| `actions/user.py` | 用户信息提取 | OCR 获取 ID 和用户名 |
| `actions/home.py` | 主页导航 | 进入开包界面 |
| `state_manager.py` | 部分（待评估） | 可能需要适配 |

---

## 5. 实现计划

### Phase 1: 基础设施（预计 2-3 小时）

- [x] 创建 `db/` 模块，实现 SQLite 连接和模型
- [x] 创建 `xml/` 模块，实现账号提取/注入
- [x] 创建 `daily/root_checker.py`，实现 root 检测
- [x] 添加 `--daily` 命令行参数

### Phase 2: 核心流程（预计 3-4 小时）

- [x] 实现 `AccountManager` 账号管理
- [x] 实现 `DailyRunner` 主流程
- [x] 实现单设备开包循环
- [ ] 集成 OCR 用户信息获取

### Phase 3: 多线程与调度（预计 2-3 小时）

- [x] 实现多设备并行开包
- [x] 实现定时扫描调度器
- [ ] 处理异常和恢复

### Phase 4: 测试与优化（预计 2 小时）

- [ ] 单设备测试
- [ ] 多设备测试
- [ ] 边界情况处理

---

## 6. 实现状态

> 更新时间：2026-01-16

### 已完成

| 模块 | 文件 | 说明 |
|------|------|------|
| db | `connection.py` | SQLite 连接管理、表初始化 |
| db | `models.py` | Account, PackRecord, AccountConfig 数据模型 |
| db | `repository.py` | CRUD 操作、待开包账号查询 |
| xml | `extractor.py` | 通过 ADB 提取 deviceAccount:.xml |
| xml | `injector.py` | 注入 XML 并重启游戏 |
| daily | `root_checker.py` | Root 检测（su -c 方式） |
| daily | `account_manager.py` | 账号增删改查、XML 哈希去重 |
| daily | `pack_opener.py` | 单设备开包执行器框架 |
| daily | `runner.py` | 多设备并行 + 守护模式定时扫描 |
| settings | `settings.py` | 添加 --daily, --db-path, --xml-dir 参数 |
| main | `main.py` | 添加 run_daily_mode_wrapper 入口 |

### 待完善（后续迭代）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| **开包逻辑** | `pack_opener.py` 中的 `open_packs()` 需要复用现有 actions 实现实际开包流程 | 高 |
| **用户信息获取** | 集成现有的 OCR 用户信息提取逻辑到 `on_user_info_needed` 回调 | 高 |
| **错误恢复** | 添加重试机制和异常恢复策略 | 中 |
| **页面检测等待** | 用 PageDetector 替代固定 sleep 等待 | 中 |
| **TUI 管理工具** | 账号配置管理界面 | 低 |

---

## 7. 决策记录

| 问题 | 决策 | 理由 |
|------|------|------|
| 数据库选型 | **SQLite 优先** | 零配置、单文件、便于开发调试，后续可扩展 PostgreSQL |
| XML 存储位置 | **文件系统** | 便于备份和手动管理，数据库只存元数据和路径 |
| TUI 工具 | **后续开发** | 先完成核心开包功能，TUI 作为独立迭代 |

---

## 7. 参考资料

- `docs/refs/08-ptcgpb-xml-account-management.md` - XML 账号管理机制
- `docs/refs/09-root-bluestacks-air.md` - BlueStacks Root 方法
