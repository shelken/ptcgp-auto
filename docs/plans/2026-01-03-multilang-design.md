# 多语言支持设计

## 概述

为 ptcgp-auto 项目添加多语言支持，包括：
1. README 多语言版本
2. 代码界面识别的多语言配置

## README 多语言

### 文件结构

```
ptcgp-auto/
├── README.md           # 中文版（主页）
├── README_EN.md        # 英文版
```

### 头部设计

两个 README 采用统一头部：

```markdown
<h3 align="center">
<img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
PTCGP Auto
</h3>

<p align="center">
  <a href="README.md">🇨🇳 中文</a> | <a href="README_EN.md">🇺🇸 English</a>
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)]()
[![macOS](https://img.shields.io/badge/macOS-only-black?style=for-the-badge&logo=apple&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)]()

</div>
```

### 语言切换链接

- 中文版：`🇨🇳 中文 | [🇺🇸 English](README_EN.md)`
- 英文版：`[🇨🇳 中文](README.md) | 🇺🇸 English`

## AGENTS.md 更新

在 **注意事项** 章节末尾添加：

```markdown
- 更新 README 时需同步更新 `README_EN.md`
```

## 代码多语言支持

### 范围

仅国际化界面识别相关配置：
- `PAGES`（界面识别规则）
- `TEXT_VARIANTS`（多语言文本变体）
- `BATTLE_LEVELS`（等级名称）

日志输出暂不国际化。

### 目录结构

```
ptcgp-auto/
├── locales/
│   ├── __init__.py     # 空文件（Python 包标识）
│   ├── zh_Hant.py      # 繁体中文（默认）
│   └── en_US.py        # 英文
├── config.py           # 添加 LANGUAGE 配置，动态加载
```

### locale 文件格式

```python
# locales/zh_Hant.py
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

PAGES = {
    "popup_ok": {
        "identifiers": ["OK", "確定", "确定"],
        ...
    },
    ...
}

TEXT_VARIANTS = {
    "continue": ["點擊來繼續", "繼續", ...],
    ...
}
```

### config.py 改动

```python
# 语言配置
LANGUAGE = "zh_Hant"  # 可选: "zh_Hant", "en_US"

# 动态加载语言包
from importlib import import_module
_locale = import_module(f"locales.{LANGUAGE}")

PAGES = _locale.PAGES
BATTLE_LEVELS = _locale.BATTLE_LEVELS
TEXT_VARIANTS = _locale.TEXT_VARIANTS
```

## 实施清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `README.md` | 重写 | 添加头部样式、徽章、语言切换链接 |
| `README_EN.md` | 新建 | 英文版 README |
| `AGENTS.md` | 修改 | 注意事项添加一行 README 同步说明 |
| `locales/__init__.py` | 新建 | 空文件（Python 包标识） |
| `locales/zh_Hant.py` | 新建 | 从 config.py 提取繁中识别文本 |
| `locales/en_US.py` | 新建 | 英文识别文本（需补充完整） |
| `config.py` | 修改 | 添加 LANGUAGE 配置，动态加载 locale |

## 注意事项

- `en_US.py` 的英文文本需要根据游戏实际英文界面补充
- 现有逻辑无需修改，只是配置来源从硬编码变为 locale 文件
