# PTCGP 自动化脚本设计文档

## 概述

这是一个用于 Pokemon TCG Pocket (PTCGP) 游戏的自动化脚本，运行在 BlueStacks Air 模拟器上，通过 ADB 进行控制。

### 技术栈

- **ADB 控制**: `adbutils` - 截图、点击、滑动
- **OCR 识别**: Apple Vision Framework - 原生 GPU 加速，支持繁体中文
- **模板匹配**: OpenCV - 识别图标按钮
- **状态管理**: JSON 文件持久化

## 游戏界面结构

```
对战主菜单
├── 與他人對戰 (多人对战)
└── 單人對戰
    ├── 咩利羊掉落活動 (限时活动)
    └── 分級對戰 (等级对战)
        ├── 初級 (进度: 15/35 或 Complete)
        ├── 中級
        ├── 高級
        └── 精英
            └── [进入某个等级]
                ├── 高級擴充包ex (当前卡包)
                │   ├── 毽子花牌組
                │   ├── 呱頭蛙牌組
                │   └── 尖牙陸鯊牌組
                └── 擴充組 (历史卡包)
                    ├── A系列
                    │   ├── 未域
                    │   ├── 天海的指引
                    │   └── ...
                    └── B系列
                        ├── 伊布花園
                        └── ...
```

## 界面识别配置 (config.py PAGES)

每个界面定义：
- `identifiers`: 用于识别的文字列表
- `templates`: 用于识别的模板图片
- `action`: 在该界面执行的动作
- `priority`: 优先级（数字越小越优先）
- `exact_match`: 是否精确匹配
- `exclude_identifiers`: 排除条件

### 界面优先级列表

| 优先级 | 界面名称 | 识别标识 | 动作 |
|--------|----------|----------|------|
| 1 | popup_ok | "OK", "確定" (精确) | click_identifier |
| 10 | battle_result_continue | "點擊來繼續" | click_identifier |
| 11 | continue_button | "繼續" | click_identifier |
| 15 | battle_record | "對戰紀錄" | click_continue |
| 16 | exp_result | "玩家經驗值", "EXP" | click_continue |
| 20 | battle_in_progress | "對戰對手" | wait |
| 30 | deck_detail | "對戰！" | start_battle |
| 42 | expansion_select | "選擇擴充組" | handle_expansion_select |
| 45 | deck_list | "擴充組" (排除選擇擴充組) | handle_deck_list |
| 50 | ranked_battle_select | "分級對戰" (排除擴充組) | select_level |
| 55 | battle_menu | "與他人對戰" | click_solo_battle |
| 60 | solo_battle_main | "單人對戰" (排除與他人對戰) | find_incomplete |

## 模板文件 (templates/)

| 模板名 | 用途 | 阈值 |
|--------|------|------|
| btn_back.png | 返回按钮 | 0.6 |
| btn_battle.png | 对战按钮 | 0.8 |
| btn_continue.png | 继续按钮 | 0.8 |
| shalou.png | 沙漏图标（表示有可领取奖励） | 0.6 |

## 状态管理 (state_manager.py)

### 状态结构 (state.json)

```json
{
  "last_updated": "2026-01-11T14:00:00",
  "current_level": "初級",
  "current_series": "A",
  "levels": {
    "初級": {
      "complete": false,
      "packs": {
        "毽子花": true,
        "呱頭蛙": false
      }
    },
    "中級": { ... },
    "高級": { ... },
    "精英": { ... }
  }
}
```

### 状态判断逻辑

1. **等级完成判断**: 单人对战页面显示 "Complete" → 该等级所有卡包完成
2. **卡包完成判断**: 进入卡包后滑动查找沙漏，无沙漏 → 该卡包当前等级完成
3. **卡包名称识别**: 在卡包牌组列表页面识别标题（如 "毽子花牌組"）

## 核心流程

### 主循环 (状态机)

```
while running:
    截图
    识别当前界面 (按优先级遍历 PAGES)
    执行对应动作
    等待页面切换
```

### 动作处理

1. **click_identifier**: 点击识别到的文字位置
2. **click_continue**: 点击屏幕中央
3. **click_template**: 点击模板匹配位置
4. **wait**: 对战中等待
5. **start_battle**: 开启自动模式 + 点击对战
6. **select_level**: 选择未完成的等级（检查进度数字）
7. **find_incomplete**: 在单人对战主页寻找未完成任务
8. **click_solo_battle**: 点击单人对战入口
9. **handle_deck_list**: 处理牌组列表（找沙漏或进扩充组）
10. **handle_expansion_select**: 处理扩充组选择（找未完成卡包，切换系列）

### 对战流程

```
牌组详情页 (有 "對戰!" 按钮)
  ↓ 检查自动模式，OFF则点击开启
  ↓ 点击 "對戰!"
对战中 (显示 "對戰對手")
  ↓ 等待...
对战结果 (显示 "勝利!" + "點擊來繼續")
  ↓ 点击继续
对战记录 (显示 "對戰紀錄")
  ↓ 点击继续
经验值结算 (显示 "玩家經驗值")
  ↓ 点击继续
返回牌组列表
```

### 扩充组遍历流程

```
牌组列表页 (有 "擴充組" 按钮)
  ↓ 查找沙漏
  ↓ 无沙漏 → 点击 "擴充組"
扩充组选择页 (显示 "選擇擴充組")
  ↓ 查找进度数字 (如 "21/30")
  ↓ 有未完成 → 点击进入
  ↓ 都是 CLEAR → 滑动查看更多
  ↓ 还没有 → 切换 A/B 系列
  ↓ 全部完成 → 点击 X 关闭
卡包牌组列表页
  ↓ 识别卡包标题
  ↓ 查找沙漏
  ↓ 有沙漏 → 点击进入对战
  ↓ 无沙漏 → 标记该卡包完成，返回扩充组选择
```

## 文件结构

```
ptcgp-auto/
├── config.py           # 配置文件（ADB、等待时间、界面识别、文本变体）
├── main.py             # 主程序（状态机、动作执行）
├── adb_controller.py   # ADB 控制封装
├── recognizer.py       # OCR 和模板匹配
├── state_manager.py    # 状态管理
├── debug_tool.py       # 调试工具（交互式测试）
├── requirements.txt    # Python 依赖
├── flake.nix           # Nix 开发环境
├── state.json          # 状态文件（运行时生成）
├── templates/          # 模板图片目录
│   ├── btn_back.png
│   ├── btn_battle.png
│   ├── btn_continue.png
│   └── shalou.png
└── debug_output/       # 调试输出目录
```

## 待完成功能

1. **卡包标题识别**: 在卡包牌组列表页面识别标题，用于状态记录
2. **X 按钮模板**: 添加扩充组选择页面的关闭按钮模板
3. **完整流程测试**: 验证整个自动化流程
4. **异常处理**: 网络断开、游戏卡死等情况

## 使用说明

### 启动

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto
python main.py
```

### 调试工具

```bash
python debug_tool.py
```

功能列表：
1. 测试 ADB 连接
2. 截图并保存
3. 截图 + OCR 识别
4. 测试查找特定文字
5. 测试多语言变体查找
6. 测试点击屏幕中央
7. 测试滑动
8. 裁剪模板图片（手动输入坐标）
9. 自动检测 UI 组件（智能识别按钮）
10. 查看当前配置

### 重置状态

删除 `state.json` 文件即可重置所有进度。
