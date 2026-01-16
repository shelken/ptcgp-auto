# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PTCGP Auto - AI 助手指引

## 最高原则

- 使用中文描述所有 文档/注释/日志输出 方便开发人员理解
- 解决问题时，执行命令前，思考当前的命令是否需要声明式配置以保证后续不再犯错，而不是直接执行
- 必要时直接通过 `python debug_tool.py -a 127.0.0.1:[PORT] --template [template_name]` 查看当前页面的ocr内容和是否出现相应模板文件
- add代码时，必须检查与本次有关的文件，不允许`add -A`
- 在coding阶段，一定要懂得模块化设计，高内聚低耦合原则，单代码文件最多不要超过500行
- **当代码结构变更时，对应更新 README 和 CLAUDE.md（本文件）**

## 知识获取与整理原则

- 使用中文书写所有文档
- 优先使用`fetcher-mcp`获取网页内容
- 调研资料时，不定时（分阶段）将获取的知识按照`[两位数字]-[主题].md`格式放入docs/refs文件夹中，方便后续重新阅读.
- 每次进行资料搜集时先列出目录已经获取的知识
- 知识不要详尽，应当大部分用一句话来总结结论，然后用具体来源的URL链接指向，尽量简洁凝练总结所有知识点，除非很重要必须详细说明。
- 知识获取来源必须用链接直接写出，方便用户和agents直接跳转获取，链接应该是具体的，而不是笼统的域名或者路径。

## 项目概述

这是一个用于 PTCGP（Pokemon TCG Pocket）单人对战的 Python 自动化脚本，运行在 Mac 上的 BlueStacks Air 模拟器。使用 ADB 进行设备控制，Apple Vision Framework OCR + OpenCV 模板匹配进行界面识别。

## 核心文件

源代码位于 `src/ptcgp_auto/` 目录下：

- `main.py` - 入口文件，支持命令行参数指定 ADB 地址
- `src/ptcgp_auto/`
  - `adb_controller.py` - ADB 封装（截图、点击、滑动）
  - `recognizer.py` - Apple Vision OCR + OpenCV 模板匹配
  - `page_detector.py` - 页面检测器，识别当前游戏界面
  - `state_manager.py` - 状态管理器，保存和加载自动化进度
  - `config.py` - 配置常量和界面识别规则
  - `settings.py` - 运行时配置加载
  - `device_discovery.py` - 设备发现
  - `logger.py` - 日志系统
  - `notifier.py` - 通知系统
  - `utils.py` - 工具函数
  - `actions/` - 动作处理器模块（模块化架构）
    - `handler.py` - ActionHandler 门面类
    - `base.py` - 基础动作（点击、等待等）
    - `battle.py` - 对战相关动作
    - `level.py` - 等级选择动作
    - `deck.py` - 牌组列表动作
    - `expansion.py` - 扩充组选择动作
    - `home.py` - 主页动作
    - `user.py` - 用户信息动作
    - `tutorial.py` - 教程动作
    - `utils/` - 工具模块（滚动、OCR辅助、导航）
  - `recognizer_parts/` - 识别器拆分模块
    - `ocr.py` - OCR 相关
    - `template_matcher.py` - 模板匹配
    - `text.py` - 文本处理
    - `color.py` - 颜色处理
  - `locales/` - 多语言配置
    - `zh_Hant.py` - 繁体中文主配置
    - `zh_Hant_pages/` - 繁体中文页面配置（按模式分离）
      - `common.py` - 通用页面
      - `user_info.py` - 用户信息页面
      - `battle.py` - 对战模式页面
      - `tutorial.py` - 教程模式页面
      - `daily.py` - 开包模式页面
    - `en_US.py` - 英文
  - `db/` - 数据库模块（每日开包功能）
    - `connection.py` - SQLite 连接管理
    - `models.py` - 数据模型
    - `repository.py` - 数据访问层
  - `xml/` - XML 账号操作（每日开包功能）
    - `extractor.py` - 账号提取
    - `injector.py` - 账号注入
  - `daily/` - 每日开包模块
    - `runner.py` - 多设备并行运行器
    - `account_manager.py` - 账号管理
    - `pack_opener.py` - 开包执行器
    - `root_checker.py` - Root 检测
  - `debug_tools/` - 调试工具实现
- `debug_tool.py` - 调试工具入口
- `templates/` - 按钮模板图片

## 架构

```
ptcgp-auto/
├── main.py                     # 主程序入口
├── debug_tool.py               # 调试工具入口
├── src/
│   └── ptcgp_auto/
│       ├── __init__.py
│       ├── adb_controller.py   # ADB 控制
│       ├── config.py           # 配置 + 模式加载
│       ├── device_discovery.py # 设备发现
│       ├── logger.py           # 日志
│       ├── notifier.py         # 通知
│       ├── page_detector.py    # 页面检测器
│       ├── recognizer.py       # OCR + 模板匹配
│       ├── settings.py         # 运行时配置
│       ├── state_manager.py    # 状态管理
│       ├── utils.py            # 工具函数
│       ├── actions/            # 动作处理器模块
│       │   ├── __init__.py
│       │   ├── handler.py          # 门面类
│       │   ├── base.py             # 基础动作
│       │   ├── battle.py           # 对战动作
│       │   ├── level.py            # 等级选择
│       │   ├── deck.py             # 牌组列表
│       │   ├── expansion.py        # 扩充组选择
│       │   ├── home.py             # 主页动作
│       │   ├── user.py             # 用户信息
│       │   ├── tutorial.py         # 教程
│       │   └── utils/              # 工具模块
│       ├── recognizer_parts/   # 识别器拆分模块
│       ├── locales/            # 多语言配置
│       │   ├── zh_Hant.py          # 繁体中文主配置
│       │   ├── zh_Hant_pages/      # 页面配置（按模式分离）
│       │   │   ├── common.py       # 通用页面
│       │   │   ├── battle.py       # 对战模式
│       │   │   ├── tutorial.py     # 教程模式
│       │   │   └── daily.py        # 开包模式
│       │   └── en_US.py
│       ├── db/                 # 数据库模块
│       ├── xml/                # XML 账号操作
│       ├── daily/              # 每日开包模块
│       └── debug_tools/        # 调试工具实现
├── templates/                  # 模板图片
└── docs/                       # 文档
    ├── 01-daily-pack-feature.md
    ├── 02-pack-opener-logic.md
    └── refs/                   # 参考资料
```

运行时架构：

```
main.py (入口 + 主循环)
    ↓
PTCGPAuto
    ├── AdbController (adb_controller.py)
    │       截图、点击、滑动、返回键
    ├── Recognizer (recognizer.py)
    │       Apple Vision OCR、OpenCV 模板匹配
    ├── PageDetector (page_detector.py)
    │       根据 OCR 和模板识别当前界面
    ├── ActionHandler (actions/)
    │       执行各界面对应的动作
    │       ├── BaseActions - 基础动作
    │       ├── BattleActions - 对战动作
    │       ├── LevelActions - 等级选择
    │       ├── DeckActions - 牌组列表
    │       ├── ExpansionActions - 扩充组选择
    │       ├── HomeActions - 主页动作
    │       ├── UserActions - 用户信息
    │       └── utils/ - 工具（滚动、OCR、导航）
    └── StateManager (state_manager.py)
            保存/加载等级和卡包完成状态
```

## 状态机流程

```
主循环:
    截图 → 识别界面 → 执行动作 → 等待 → 重复

界面识别按优先级排序（config.PAGES），支持：
- 文字标识符匹配（精确/包含）
- 模板图片匹配
- 排除条件
```

## 常用命令

```bash
# 环境初始化
nix develop                    # 推荐，自动创建 venv 并安装依赖
direnv allow                   # 或使用 direnv
pip install -r requirements.txt  # 手动安装（需 Python 3.10+）

# 运行主程序
python main.py                 # 默认连接 127.0.0.1:5555，繁体中文
python main.py -a 5556         # 指定端口
python main.py -l en_US        # 使用英文界面
python main.py -a 5556 -l en_US  # 指定端口和语言

# 调试工具
python debug_tool.py           # 交互式调试（OCR 测试、截图、滑动等）
python debug_tool.py -a 5556

# 重置进度
rm /tmp/ptcgp_auto_5555/state.json
```

## 多设备支持

每个设备使用独立的数据目录 `/tmp/ptcgp_auto_{port}/`，包含 `state.json` 和调试截图。

## 配置说明

关键配置项（config.py）：
- `BATTLE_LEVELS` - 等级遍历顺序（默认精英→初级）
- `WAIT_BATTLE_CHECK_INTERVAL` - 对战中检测间隔
- `PAGES` - 界面识别规则（由 `load_mode()` 动态加载）
- `CURRENT_MODE` - 当前运行模式（battle/tutorial/daily）

### 模式系统

支持三种运行模式，每种模式加载不同的页面配置：

| 模式 | 入口参数 | 页面数 | 说明 |
|------|----------|--------|------|
| `battle` | 默认 | 26 | 自动对战（含教程检测） |
| `tutorial` | `-t` | 8 | 教程解锁模式 |
| `daily` | `--daily` | 10+ | 每日开包模式 |

切换模式：
```python
from ptcgp_auto import config
config.load_mode("daily")  # 加载每日开包模式的页面
```

## 调试技巧

1. 使用 `debug_tool.py` 进行交互式调试
2. 设置 `config.DEBUG = True` 查看详细日志
3. OCR 结果格式：`"文字"@(x, y)`
4. 模板匹配会显示最高置信度

## 扩展新页面

1. 根据页面所属模式，在 `locales/zh_Hant_pages/` 对应文件中添加页面定义
   - `common.py` - 所有模式共享的页面
   - `battle.py` - 对战模式专用
   - `tutorial.py` - 教程模式专用
   - `daily.py` - 开包模式专用
2. 在 `actions/` 对应模块中实现动作方法，并在 `actions/handler.py` 中添加委托方法

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- BlueStacks Air 的 ADB 端口通常是 5555，但可能有所不同
- 模板图片通过 debug_tool.py 的自动检测功能截取
- 状态文件保存在系统临时目录，重启系统后可能被清理
- 更新 README 时需同步更新 `README_EN.md`
- 新功能开发使用 git worktree 创建独立分支，完成后提交 PR 合并

## 清理 BlueStacks VM 中的 PTCGP 用户数据

当需要制作干净的 VM 模板（保留游戏资源但清除用户登录数据）时，使用以下步骤：

### 前置条件

1. 已安装 Lima：`brew install lima`
2. 已创建 Lima Ubuntu VM（配置文件：`lima-ubuntu.yaml`）
3. 目标 BlueStacks VM 已关闭

### 启动 Lima VM

```bash
# 首次创建
limactl create --name=ubuntu-qcow2 lima-ubuntu.yaml
limactl start ubuntu-qcow2

# 后续使用
limactl start ubuntu-qcow2
```

### 清理 PTCGP 用户数据

```bash
# 替换 Tiramisu64_XX 为目标 VM 名称（如 Tiramisu64_10）
limactl shell ubuntu-qcow2 -- bash -c "sudo guestfish -a /bluestacks/Tiramisu64_XX/data.qcow2 run : mount /dev/sda1 / : rm-rf /data/jp.pokemon.pokemontcgp/shared_prefs : rm-rf /data/jp.pokemon.pokemontcgp/databases : rm-rf /data/jp.pokemon.pokemontcgp/files : rm-rf /data/jp.pokemon.pokemontcgp/no_backup : rm-rf /data/jp.pokemon.pokemontcgp/cache : rm-rf /data/jp.pokemon.pokemontcgp/code_cache : rm-rf /data/jp.pokemon.pokemontcgp/app_databases : rm-rf /data/jp.pokemon.pokemontcgp/app_webview : rm-rf /data/jp.pokemon.pokemontcgp/app_textures"
```

### 验证清理结果

```bash
limactl shell ubuntu-qcow2 -- bash -c "sudo guestfish --ro -a /bluestacks/Tiramisu64_XX/data.qcow2 run : mount /dev/sda1 / : ll /data/jp.pokemon.pokemontcgp/"
# 应该只显示空目录（仅 . 和 ..）
```

### VM 名称对照

查看 BlueStacks 配置获取 VM 名称：
```bash
grep 'display_name' "/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf"
```

### 停止 Lima VM

```bash
limactl stop ubuntu-qcow2
```

## 参考文档

- `docs/design.md`: 详细设计文档（游戏界面结构、状态机流程、界面优先级表）
