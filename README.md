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

# 调试工具
python debug_tool.py
python debug_tool.py -a 5556
```

## 配置

编辑 `config.py`：

```python
# 语言配置（可选: "zh_Hant", "en_US"）
LANGUAGE = "zh_Hant"

# 对战中检测间隔（秒）
WAIT_BATTLE_CHECK_INTERVAL = 10
```

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
├── main.py             # 主程序入口
├── actions.py          # 动作处理器
├── page_detector.py    # 页面检测器
├── state_manager.py    # 状态管理
├── adb_controller.py   # ADB 控制
├── recognizer.py       # OCR + 模板匹配
├── config.py           # 配置
├── locales/            # 多语言配置
│   ├── zh_Hant.py      # 繁体中文
│   └── en_US.py        # 英文
├── debug_tool.py       # 调试工具
└── templates/          # 模板图片
```

## 注意事项

- 目前仅支持 macOS（依赖 Apple Vision Framework），后续计划支持其他平台
- 游戏语言需与 `config.py` 中的 `LANGUAGE` 配置一致
- 启动脚本前，请确保游戏已进入对战菜单页面

## License

MIT
