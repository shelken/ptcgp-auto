# PTCGP Auto - AI 助手指引

## 项目概述

这是一个用于 PTCGP（Pokemon TCG Pocket）单人对战的 Python 自动化脚本，运行在 Mac 上的 BlueStacks Air 模拟器。使用 ADB 进行设备控制，OCR + 模板匹配进行界面识别。

## 核心文件

- `main.py` - 入口文件，主循环逻辑
- `adb_controller.py` - ADB 封装（截图、点击、滑动）
- `recognizer.py` - OCR + 模板匹配识别
- `config.py` - 配置常量
- `templates/` - 按钮模板图片

## 架构

```
ADB 控制器 (adb_controller.py)
    ↓ 截图、点击、滑动
识别器 (recognizer.py)
    ↓ OCR 文字、模板位置
主逻辑 (main.py)
    ↓ 对战流程控制
```

## 开发说明

- BlueStacks Air 的 ADB 端口通常是 5555，但可能有所不同
- 模板图片需要手动从游戏中截取保存
- OCR 使用 easyocr 以获得更好的游戏字体识别准确率
- 调试模式会将截图保存到 `debug_output/` 目录

## 测试步骤

1. 确保 BlueStacks Air 正在运行且 PTCGP 已打开
2. 验证 ADB 连接: `adb connect 127.0.0.1:5555`
3. 运行 `python main.py` 启动自动化

## 开发环境

使用 Nix Flake 管理开发环境：

```bash
# 进入开发环境
nix develop

# 或使用 direnv
direnv allow
```
