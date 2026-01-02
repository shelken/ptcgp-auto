# PTCGP Auto

Pokemon TCG Pocket 单人对战自动化脚本，运行在 Mac + BlueStacks Air 模拟器。

## 功能

- 自动单人对战
- 支持多设备同时控制

## 技术栈

- **ADB 控制**: adbutils
- **OCR**: Apple Vision Framework (GPU 加速)
- **模板匹配**: OpenCV
- **状态管理**: JSON

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
# 等级遍历顺序
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

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
├── debug_tool.py       # 调试工具
└── templates/          # 模板图片
```

## 注意事项

- 需要 BlueStacks Air 开启 ADB 调试
- 游戏语言需设为繁体中文
- 仅支持 macOS (Apple Vision Framework)

## License

MIT
