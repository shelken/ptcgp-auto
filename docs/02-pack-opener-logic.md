# 开包逻辑完善设计文档

> 创建时间：2026-01-16
> 状态：**Phase 1 完成（模式架构重构）**
> 前置文档：`docs/01-daily-pack-feature.md`

## 1. 目标

完善 `pack_opener.py` 中的开包逻辑，复用现有的 `actions/` 模块实现实际的开包流程。

---

## 2. 模式架构（已完成）

### 2.1 设计理念

引入**模式（Mode）**概念，将 PAGES 配置按模式分离，不同模式加载不同的页面集合。

### 2.2 三种模式

| 模式 | 入口 | 页面数 | 说明 |
|------|------|--------|------|
| `battle` | 默认 | 26 | 自动对战（含教程检测和用户信息获取） |
| `tutorial` | `-t` | 8 | 教程解锁模式 |
| `daily` | `--daily` | 10 | 每日开包模式 |

### 2.3 页面组合

```
battle:   COMMON(6) + USER_INFO(3) + BATTLE(15) + TUTORIAL(2) = 26
tutorial: COMMON(6) + TUTORIAL(2) = 8
daily:    COMMON(6) + USER_INFO(3) + DAILY(1+) = 10+
```

### 2.4 文件结构

```
src/ptcgp_auto/locales/
├── zh_Hant.py              # 主配置（BATTLE_LEVELS, SERIES, TEXT_PATTERNS, MODES）
├── zh_Hant_pages/          # 繁体中文页面配置
│   ├── __init__.py         # 导出所有 PAGES_*
│   ├── common.py           # PAGES_COMMON - 通用页面
│   ├── user_info.py        # PAGES_USER_INFO - 用户信息页面
│   ├── battle.py           # PAGES_BATTLE - 对战模式页面
│   ├── tutorial.py         # PAGES_TUTORIAL - 教程模式页面
│   └── daily.py            # PAGES_DAILY - 开包模式页面
└── en_US.py                # 英文配置（暂未拆分）
```

### 2.5 使用方式

```python
from ptcgp_auto import config

# 加载对战模式（默认）
config.load_mode("battle")

# 加载每日开包模式
config.load_mode("daily")

# 加载教程模式
config.load_mode("tutorial")

# 查看当前模式
print(config.CURRENT_MODE)  # "battle"
print(len(config.PAGES))    # 26
```

---

## 3. 开包流程（待实现）

### 3.1 用户确认的流程

```
主页 → 开包图标 → 系列/扩充组选择 → 选择卡包 → 开包动画 → 自动返回主页
```

### 3.2 免费包机制

| 属性 | 说明 |
|------|------|
| 刷新周期 | 每 12 小时刷新 1 个 |
| 每日上限 | 一天最多 2 个免费包 |
| 可用检测 | 主页有特定图标表示是否有免费包可开 |

### 3.3 待添加的页面

| 页面 | 说明 | 状态 |
|------|------|------|
| `game_home_main` | 游戏主页（开包入口） | ✓ 已定义 |
| `pack_series_select` | 系列选择页面 | 待探索 |
| `pack_list` | 卡包列表页面 | 待探索 |
| `pack_opening` | 开包动画页面 | 待探索 |

---

## 4. 下一步

- [ ] 使用 debug tool 探索开包界面
- [ ] 截取开包图标模板
- [ ] 截取免费包可用标识
- [ ] 补充 `pages/daily.py` 中的页面定义
- [ ] 实现 `pack_opener.py` 中的开包状态机
