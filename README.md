<h3 align="center">
<img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
PTCGP Auto
</h3>

<p align="center">
  🇨🇳 中文 | <a href="README_EN.md">🇺🇸 English</a>
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-8AADF4?style=for-the-badge&logo=python&logoColor=white&labelColor=363a4f)]()
[![macOS](https://img.shields.io/badge/macOS-only-CAD3F5?style=for-the-badge&logo=apple&logoColor=white&labelColor=363a4f)]()
[![License](https://img.shields.io/badge/License-MIT-A6DA95?style=for-the-badge&labelColor=363a4f)]()

</div>

---

Pokemon TCG Pocket 单人对战自动化脚本，支持任何可通过 ADB 连接的 Android 设备或模拟器。

## 功能

- 自动单人对战（分级对战）
- 按优先级自动遍历等级和卡包
- 支持多设备同时控制
- **每日开包模式**（开发中）- 自动轮换账号开免费包

## 运行模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 对战模式 | `python main.py` | 默认模式，自动单人对战 |
| 教程模式 | `python main.py -t` | 解锁单人对战的教程流程 |
| 每日开包 | `python main.py --daily` | 轮换账号开免费包（需 root） |

## 技术栈

- **ADB 控制**: adbutils
- **OCR**: Apple Vision Framework (GPU 加速)
- **模板匹配**: OpenCV
- **状态管理**: JSON

## 前置条件

- 设备需开启 ADB 调试
- 游戏语言需设为**繁体中文**（或配置对应语言）
- **启动前需手动进入游戏对战页面**（能看到"單人對戰"按钮的界面）

## 安装

### 使用 Nix (推荐)

```bash
nix develop
# 或
direnv allow
```

### 手动安装

```bash
pip install -r requirements.txt
```

依赖：
- Python 3.10+
- adbutils
- opencv-python
- Pillow
- pyobjc-framework-Vision (macOS)

## 使用

```bash
# 默认连接 127.0.0.1:5555
python main.py

# 指定 ADB 地址
python main.py -a 5556
python main.py -a 192.168.1.100:5555

# v2：未指定 -d 时自动发现 BlueStacks 设备
python main_v2.py --daemon

# v2：手动切换账号（支持端口简写，勿与 --task/--daemon 同时使用）
python main_v2.py --switch-account 4 -d 5715

# 调试工具
python debug_tool.py
python debug_tool.py -a 5556
```

## 配置

编辑 `config.py` 查看和修改所有配置项，包括：
- `LANGUAGE` - 语言配置（可选: "zh_Hant", "en_US"）
- `WAIT_BATTLE_CHECK_INTERVAL` - 对战中检测间隔
- `DEBUG` - 调试模式

## 多设备

每个设备使用独立的临时目录：

```
/tmp/ptcgp_auto_5555/state.json
/tmp/ptcgp_auto_5556/state.json
```

重置进度：
```bash
rm /tmp/ptcgp_auto_5555/state.json
```

## 文件结构

```
ptcgp-auto/
├── main.py                 # 主程序入口
├── debug_tool.py           # 调试工具入口
├── src/
│   └── ptcgp_auto/
│       ├── __init__.py
│       ├── runner.py       # 主流程状态机
│       ├── actions/        # 动作处理器模块
│       │   ├── __init__.py     # 导出 ActionHandler
│       │   ├── handler.py      # 门面类
│       │   ├── base.py         # 基础动作
│       │   ├── battle.py       # 对战动作
│       │   ├── level.py        # 等级选择
│       │   ├── deck.py         # 牌组列表
│       │   ├── expansion.py    # 扩充组选择
│       │   ├── home.py         # 主页动作
│       │   └── utils/          # 工具模块
│       │       ├── scroll.py       # 滚动辅助
│       │       ├── ocr_helpers.py  # OCR 工具
│       │       └── navigation.py   # 导航工具
│       ├── adb_controller.py   # ADB 控制
│       ├── config.py           # 配置（含模式加载）
│       ├── daily/              # 每日开包模块
│       │   ├── __init__.py
│       │   ├── runner.py       # 每日模式运行器
│       │   └── pack_opener.py  # 开包逻辑
│       ├── db/                 # 数据库模块
│       │   ├── __init__.py
│       │   └── account_db.py   # 账号数据库
│       ├── debug_tools/        # 调试工具实现
│       ├── device_discovery.py # 设备发现
│       ├── locales/            # 多语言配置
│       │   ├── zh_Hant.py          # 繁体中文主配置
│       │   ├── zh_Hant_pages/      # 繁体中文页面配置
│       │   │   ├── __init__.py     # 导出所有页面组
│       │   │   ├── common.py       # 通用页面
│       │   │   ├── user_info.py    # 用户信息页面
│       │   │   ├── battle.py       # 对战模式页面
│       │   │   ├── tutorial.py     # 教程模式页面
│       │   │   └── daily.py        # 开包模式页面
│       │   └── en_US.py            # 英文配置
│       ├── logger.py           # 日志
│       ├── notifier.py         # 通知
│       ├── page_detector.py    # 页面检测器
│       ├── recognizer.py       # OCR + 模板匹配
│       ├── recognizer_parts/   # 识别器拆分模块
│       ├── settings.py         # 运行时配置
│       ├── state_manager.py    # 状态管理
│       └── utils.py            # 工具函数
├── templates/              # 模板图片
└── docs/                   # 文档
```

## 注意事项

- 目前仅支持 macOS（依赖 Apple Vision Framework），后续计划支持其他平台
- 游戏语言需与 `config.py` 中的 `LANGUAGE` 配置一致
- 启动脚本前，请确保游戏已进入对战菜单页面
- **截取模板图片时，模拟器分辨率必须为 1080p**（脚本会根据实际分辨率自动缩放模板）

## License

MIT
