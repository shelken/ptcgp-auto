# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PTCGP Auto - AI 助手指引

## 项目概述

这是一个用于 PTCGP（Pokemon TCG Pocket）单人对战的 Python 自动化脚本，运行在 Mac 上的 BlueStacks Air 模拟器。使用 ADB 进行设备控制，Apple Vision Framework OCR + OpenCV 模板匹配进行界面识别。

## 核心文件

- `main.py` - 入口文件，支持命令行参数指定 ADB 地址
- `adb_controller.py` - ADB 封装（截图、点击、滑动）
- `recognizer.py` - Apple Vision OCR + OpenCV 模板匹配
- `page_detector.py` - 页面检测器，识别当前游戏界面
- `actions.py` - 动作处理器，处理各种界面操作
- `state_manager.py` - 状态管理器，保存和加载自动化进度
- `config.py` - 配置常量和界面识别规则
- `utils.py` - 工具函数
- `debug_tool.py` - 交互式调试工具
- `templates/` - 按钮模板图片

## 架构

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
    ├── ActionHandler (actions.py)
    │       执行各界面对应的动作
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
python main.py                 # 默认连接 127.0.0.1:5555
python main.py -a 5556         # 指定端口
python main.py -a 192.168.1.100:5555  # 指定完整地址

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
- `WAIT_BATTLE_CHECK_INTERVAL` - 对战中检测间隔（默认10秒）
- `PAGES` - 界面识别规则（优先级、标识符、动作）

## 调试技巧

1. 使用 `debug_tool.py` 进行交互式调试
2. 设置 `config.DEBUG = True` 查看详细日志
3. OCR 结果格式：`"文字"@(x, y)`
4. 模板匹配会显示最高置信度

## 扩展新页面

1. 在 `config.py` 的 `PAGES` 中添加识别规则（identifiers/templates、action、priority）
2. 在 `actions.py` 中实现对应的动作方法

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- BlueStacks Air 的 ADB 端口通常是 5555，但可能有所不同
- 模板图片通过 debug_tool.py 的自动检测功能截取
- 状态文件保存在系统临时目录，重启系统后可能被清理

## 参考文档

- `docs/design.md`: 详细设计文档（游戏界面结构、状态机流程、界面优先级表）
