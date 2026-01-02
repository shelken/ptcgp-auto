# PTCGP 自动化脚本设计文档

## 概述

这是一个用于 Pokemon TCG Pocket (PTCGP) 游戏的自动化脚本，运行在 BlueStacks Air 模拟器上，通过 ADB 进行控制。

### 技术栈

- **ADB 控制**: `adbutils` - 截图、点击、滑动
- **OCR 识别**: Apple Vision Framework - 原生 GPU 加速，支持繁体中文
- **模板匹配**: OpenCV - 识别图标按钮
- **状态管理**: JSON 文件持久化（临时目录）

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
| 2 | battle_defeat_popup | "前往任務" | click_cancel |
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
| btn_close.png | 关闭按钮 (X) | 0.6 |
| shalou.png | 沙漏图标（表示有未完成牌组） | 0.6 |

## 状态管理 (state_manager.py)

### 状态文件位置

每个设备使用独立的临时目录：
- `/tmp/ptcgp_auto_{port}/state.json`

### 状态结构

```json
{
  "last_updated": "2026-01-11T14:00:00",
  "current_level": "初級",
  "current_series": "A",
  "levels": {
    "初級": {
      "complete": false,
      "packs": {
        "高級擴充包ex": true,
        "未域": false
      }
    },
    "中級": { ... },
    "高級": { ... },
    "精英": { ... }
  }
}
```

### 状态判断逻辑

1. **等级完成判断**: 分级对战页面显示 "Complete" → 该等级所有卡包完成
2. **卡包完成判断**: 进入卡包后滑动查找沙漏，无沙漏 → 该卡包当前等级完成
3. **卡包名称识别**: 从 "毽子花牌組（高級擴充包ex）" 中提取 "高級擴充包ex"

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
3. **click_cancel**: 点击取消按钮
4. **click_template**: 点击模板匹配位置
5. **wait**: 对战中等待
6. **start_battle**: 开启自动模式 + 点击对战
7. **select_level**: 按配置顺序选择未完成等级（支持滑动）
8. **find_incomplete**: 在单人对战主页寻找未完成任务
9. **click_solo_battle**: 点击单人对战入口
10. **handle_deck_list**: 处理牌组列表（找沙漏或进扩充组）
11. **handle_expansion_select**: 处理扩充组选择（找未完成卡包，切换系列）

### 对战流程

```
牌组详情页 (有 "對戰!" 按钮)
  ↓ 检查自动模式，OFF则点击开启
  ↓ 点击 "對戰!"
对战中 (显示 "對戰對手")
  ↓ 等待...
对战结果 (显示 "勝利!" + "點擊來繼續")
  ↓ 点击继续
[如果战败: 显示 "前往任務" + "取消"]
  ↓ 点击取消
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
  ↓ 有沙漏 → 点击进入对战
  ↓ 无沙漏 → 标记当前卡包完成 → 点击 "擴充組"
扩充组选择页 (显示 "選擇擴充組")
  ↓ 查找进度数字 (如 "21/30")
  ↓ 有未完成且未尝试 → 记录并点击进入
  ↓ 都已尝试或 CLEAR → 滑动查看更多
  ↓ 还没有 → 切换 A/B 系列
  ↓ 全部完成 → 点击 X 关闭
卡包牌组列表页
  ↓ 识别卡包标题
  ↓ 查找沙漏
  ↓ 有沙漏 → 点击进入对战
  ↓ 无沙漏 → 标记该卡包完成，点击擴充組继续
```

## 文件结构

```
ptcgp-auto/
├── main.py             # 主程序入口（状态机、命令行参数）
├── adb_controller.py   # ADB 控制封装
├── recognizer.py       # OCR 和模板匹配
├── page_detector.py    # 页面检测器
├── actions.py          # 动作处理器
├── state_manager.py    # 状态管理
├── config.py           # 配置文件（ADB、等待时间、界面识别）
├── utils.py            # 工具函数
├── debug_tool.py       # 调试工具（交互式测试）
├── requirements.txt    # Python 依赖
├── flake.nix           # Nix 开发环境
├── AGENTS.md           # AI 助手指引
├── templates/          # 模板图片目录
│   ├── btn_back.png
│   ├── btn_close.png
│   └── shalou.png
└── docs/
    └── design.md       # 本设计文档
```

## 多设备支持

```bash
# 同时控制多个模拟器
python main.py -a 5555  # 第一个模拟器
python main.py -a 5556  # 第二个模拟器

# 每个设备有独立的数据目录
/tmp/ptcgp_auto_5555/
├── state.json
└── *.png

/tmp/ptcgp_auto_5556/
├── state.json
└── *.png
```

## 使用说明

### 启动

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto
python main.py
python main.py -a 5556  # 指定端口
```

### 调试工具

```bash
python debug_tool.py
python debug_tool.py -a 5556
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

删除对应端口的状态文件即可：
```bash
rm /tmp/ptcgp_auto_5555/state.json
```
