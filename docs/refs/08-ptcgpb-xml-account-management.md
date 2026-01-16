# PTCGPB XML 账号管理机制

> 来源：`_out/PTCGPB/` 代码库分析

## 核心原理

PTCGP 游戏的账号数据存储在安卓系统的 **SharedPreferences** 中：

```
/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml
```

通过 ADB 提取/注入这个 XML 文件，即可实现账号的备份和切换。

---

## 1. 账号提取（Extract）

**脚本**: `Accounts/_ExtractAccount.ahk`

**流程**:
1. 通过 GUI 输入模拟器实例名称和保存文件名
2. 使用 ADB shell 获取 root 权限（`su`）
3. 将 XML 从 `shared_prefs` 复制到 `/sdcard/`
4. 使用 `adb pull` 将 XML 拉取到本地
5. 自动删除模拟器内的账号数据（清空以便注入新账号）

**关键 ADB 命令**:
```bash
# 复制到 sdcard（非 root 可访问区域）
cp /data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml /sdcard/deviceAccount.xml

# 拉取到本地
adb pull /sdcard/deviceAccount.xml <本地路径>

# 删除原账号（可选）
rm /data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml
```

---

## 2. 账号注入（Inject）

**脚本**: `Accounts/_InjectAccount.ahk`

**流程**:
1. 通过 GUI 输入模拟器实例名称和要加载的 XML 文件名
2. 使用 ADB 强制关闭游戏
3. 使用 `adb push` 将 XML 推送到 `/sdcard/`
4. 使用 ADB shell（需 root）将 XML 复制到 `shared_prefs` 目录
5. 启动游戏

**关键 ADB 命令**:
```bash
# 关闭游戏
am force-stop jp.pokemon.pokemontcgp

# 推送 XML 到 sdcard
adb push <本地XML> /sdcard/deviceAccount.xml

# 复制到 shared_prefs（需要 root）
cp /sdcard/deviceAccount.xml /data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml

# 清理临时文件
rm /sdcard/deviceAccount.xml

# 启动游戏
am start -n jp.pokemon.pokemontcgp/com.unity3d.player.UnityPlayerActivity
```

---

## 3. 自动化账号轮换（`Scripts/1.ahk`）

### 目录结构

```
Accounts/
├── Saved/
│   ├── 0/<instance>/*.xml   # 日期 mod 3 = 0
│   ├── 1/<instance>/*.xml   # 日期 mod 3 = 1
│   └── 2/<instance>/*.xml   # 日期 mod 3 = 2
├── GodPacks/                 # God Pack 账号
├── SpecificCards/            # 特定卡牌账号（Crown、Shiny 等）
└── Trades/                   # 可交易卡牌账号
```

### 核心函数

#### `loadAccount()`
- 计算当前日期对 3 取模，选择对应的 `Saved/` 子目录
- 从 `list.txt` 读取 XML 列表（只加载 >24 小时未修改的账号）
- 通过 ADB 注入 XML 到模拟器
- 更新文件修改时间，防止重复使用

#### `saveAccount(file)`
根据账号类型保存到不同目录：

| file 参数 | 保存目录 | 用途 |
|-----------|----------|------|
| `"All"` | `Saved/{0\|1\|2}/<instance>/` | 普通账号轮换池 |
| `"Valid"` / `"Invalid"` | `GodPacks/` | God Pack 账号 |
| `"Tradeable"` | `Trades/` | 可交易卡牌账号 |
| 其他（如 `"Crown"`、`"Shiny"`） | `SpecificCards/` | 特殊卡牌账号 |

**文件命名格式**: `<时间戳>_<实例名>_<类型>_<开包数>_packs.xml`

#### `createAccountList(instance)`
- 扫描对应日期目录下的所有 XML
- 筛选 >24 小时未使用的账号写入 `list.txt`
- 用于账号轮换复用

---

## 4. 工作流程

```
┌──────────────────────────────────────────────────────────────────┐
│                     账号生命周期                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. 新账号 → 开包 → saveAccount("All") → Saved/{0|1|2}/         │
│                                                                   │
│  2. 24小时后 → loadAccount() → 从 list.txt 读取 → 注入模拟器    │
│                                                                   │
│  3. 开包结果判定:                                                 │
│     ├─ God Pack    → saveAccount("Valid") → GodPacks/           │
│     ├─ 特殊卡      → saveAccount("Crown") → SpecificCards/      │
│     ├─ 可交易      → saveAccount("Tradeable") → Trades/         │
│     └─ 普通        → saveAccount("All") → 继续轮换               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 关键技术点

| 要点 | 说明 |
|------|------|
| **需要 Root** | ADB shell 需要 `su` 才能访问 `/data/data/` |
| **XML 路径** | `deviceAccount:.xml`（注意冒号是文件名的一部分） |
| **24小时冷却** | 通过文件修改时间判断，防止重复使用同一账号 |
| **日期轮换** | `daysSinceBase % 3` 实现三天一轮的账号池隔离 |
| **实例隔离** | 每个模拟器实例有独立的 XML 存储目录 |

---

## 6. 适配到 macOS + BlueStacks

对于本项目（macOS + BlueStacks Air），需要注意：

1. **ADB 路径**: BlueStacks 的 ADB 位置与 MuMu 不同
2. **Root 权限**: BlueStacks 可能需要额外配置才能获得 root
3. **替代方案**: 可使用 Lima VM + guestfish 直接操作 qcow2 磁盘镜像（参见 `04-lima-vm.md`）

### 使用 guestfish 清理账号数据

```bash
limactl shell ubuntu-qcow2 -- bash -c "sudo guestfish -a /bluestacks/Tiramisu64_XX/data.qcow2 \
  run : mount /dev/sda1 / \
  : rm-rf /data/jp.pokemon.pokemontcgp/shared_prefs \
  : rm-rf /data/jp.pokemon.pokemontcgp/databases \
  : rm-rf /data/jp.pokemon.pokemontcgp/files"
```
