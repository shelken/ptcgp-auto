# 常见问题（FAQ）

面向使用者的常见问题与行为说明。安装与命令用法见 [README](../../README.md)。

---

## 安装与上手

### Q: `cd` 进项目目录就报 `mise ERROR ... not trusted`，是装错了吗？

不是出错，是 mise 的安全机制：未信任的 `mise.toml` 不会被加载。所有用 mise 的项目首次 clone 后都这样。

在项目根目录执行一次即可：

```bash
mise trust
```

之后 shell integration 会在每次进入目录时自动加载工具版本与 `.venv`。

### Q: 执行了 `mise trust`，为什么还要再跑 `mise run setup`？

`mise trust` 会顺带创建一个**空** `.venv`（只是个干净的虚拟环境），此时 Python 依赖还没装。直接运行程序会因找不到依赖报错。

`mise run setup` 内部执行 `uv sync` + `prek install`，才算把依赖装进 `.venv`。两者缺一不可：

```bash
mise trust          # ① 信任配置 + 建空 venv
mise run setup      # ② 装依赖 + 装 git hook
```

### Q: 没有启动 BlueStacks 模拟器，`--daemon` 能跑吗？

能。守护模式启动时会自动发现设备，发现不到就去启动 `display_name` 以 `auto-` 开头的 BlueStacks 实例。所以前提是 BlueStacks 里至少有一个 `auto-` 前缀的实例，且已配置好 Root。

退出 daemon（Ctrl+C）时，这些由守护进程**本次启动起来的** `auto-` 实例会被自动关闭，这是正常清理逻辑，不是崩溃。

### Q: BlueStacks Air 怎么装？怎么 Root？实例怎么命名才会被自动管理？

本项目的账号 XML 提取、环境重置都依赖安卓 Root，所以 BlueStacks Air 必须 Root。下面是完整的环境准备步骤。

#### 1. 安装 BlueStacks Air

从官网下载 macOS 版（仅支持 Apple Silicon，需 macOS 11+ / 8GB 内存 / 12GB 存储）：

```
https://www.bluestacks.com/mac
```

装好后**先启动一次**完成初始化，然后退出。

#### 2. Root（基于 Kitsune Magisk）

使用开源项目 [hanreev/root-bluestacks-air](https://github.com/hanreev/root-bluestacks-air)，配合 [Kitsune Magisk](https://github.com/1q23lyc45/KitsuneMagisk/releases)（已测版本 v27.2-kitsune-4）。

步骤：

1. 下载并解压 `root-bluestacks-air` 仓库
2. 把下载的 Kitsune Mask apk 重命名为 `magisk.apk` 放进项目目录
3. 确认 SIP 状态（`csrutil status`），按情况选一种：

   **SIP 开启（默认）**——生成补丁镜像后手动替换：

   ```bash
   cd ~/Downloads/root-bluestacks-air
   bash root.sh -o files/initrd_hvf.img -b files/backup
   # 把生成的 files/initrd_hvf.img 复制替换 /Applications/BlueStacks.app/Contents/img/initrd_hvf.img
   ```

   **SIP 已关闭**——一键执行（会自动替换并启动）：

   ```bash
   sudo bash root.sh
   ```

4. 启动 BlueStacks Air，安装 `magisk.apk`
5. 打开 Kitsune Mask，弹出「Requires Additional Setup」时点 **OK**，BlueStacks 会重启
6. 重启后即完成 Root；需要 Zygisk 可在 Kitsune Mask 设置里开启再重启

> 想还原：SIP 开启时把 `files/backup` 里的原始 `initrd_hvf.img` 拷回原路径即可。

#### 3. 安装游戏 APK

游戏包名固定为 `jp.pokemon.pokemontcgp`，任意来源的 APK 都行。加速版仅用于跳过动画提速，本项目的自动化流程**不依赖**加速功能：

- 官方版：Google Play / QooApp
- 加速版（可选）：[9mod.com - Pokémon TCG Pocket](https://9mod.com/pokemon-tcg-pocket.html) 等第三方站

#### 4. 命名实例为 `auto-` 前缀

只有 `display_name` 以 `auto-` 开头的实例才会被守护进程自动启动/关闭和扩缩容。

在 BlueStacks 多实例管理器（Multi-Instance Manager）里新建或选中实例 → 改名为 `auto-1`、`auto-2` 等。改完后配置文件 `bluestacks.conf` 里的 `bst.instance.<name>.display_name` 会同步更新。

> 实例的内部 name（配置里的 key）和 display_name 是两个字段，自动管理只看 display_name 前缀。

#### 5. 推荐实例参数

在 BlueStacks 多实例管理器里编辑实例设置，按以下参数配置（平衡资源占用与识别准确率）：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 分辨率 | 720×1280 | 比基准 1080×1920 省资源；代码会按分辨率自动缩放坐标（`当前/基准` 比例） |
| DPI | **320（不要改）** | 模板图片是在 320 DPI 下截取的。改 DPI 会改变游戏 UI 元素在截图中的像素占比，导致模板匹配命中率下降 |
| FPS | 30 | 截图采样足够，更高 FPS 纯耗资源 |
| CPU 核心 | 4 | |
| 内存 | 2 GB | |

> **DPI 为什么不能改？** 代码本身不读取 DPI，但截图的内容受 DPI 影响：Android 按 dp 渲染 UI，DPI 决定 dp→px 换算。模板图片是在 320 DPI 下截取的基准尺寸，改了 DPI，同一个按钮/图标在截图里占的像素数就变了，和模板对不上。这是实测过的坑，不是理论推测。

#### 6. 验证

Root 成功后，`adb shell su -c 'id'` 应返回 `uid=0`。本项目用 `--debug` 启动时会打印设备 Root 状态。

```bash
uv run python main_v2.py --daemon --debug
```

日志里看到「自动发现设备」并出现 `auto-` 实例端口，说明环境就绪。

---

## 运行时自动行为

这几个行为不需要手动触发，daemon 首次启动或扫描时会自动完成。新用户看到对应日志属于正常现象。

### Q: daemon 启动时日志里在「同步卡牌元数据」，这是什么？

新用户首次启动时，数据库 `cards` 表是空的，卡牌识别（YOLO + 感知哈希）没有元数据可匹配。

守护进程检测到元数据为空时，会自动从 `shelken/ptcgp-assets` 仓库拉取全量系列/卡包/卡牌元数据入库。这是一次性行为，后续启动检测到已有数据就跳过。

> 元数据只含卡牌的基础信息（系列、编号、名称等），**不包含**卡牌图片和哈希值。

### Q: 为什么新账号入库后不用手动建任务计划？

数据库初始化时会自动种入一个名为 `base` 的默认任务计划，包含 3 个低风险日常任务：

| 任务 | 作用 | 默认间隔 |
|------|------|----------|
| `fetch_account_info` | 同步账号资源/等级 | 24h |
| `open_pack` | 开包 | 24h |
| `collect_account_cards` | 扫描持有卡牌 | 7d |

新账号入库后自动关联该计划，开箱即用。需要更多任务（如得卡挑战、送卡、领奖励），通过 Web 界面或 `--add-plan` 增配即可。

### Q: 首次扫描某系列卡牌时，为什么下载的是几百 KB 的 JSON 而不是几个 G 的卡图？

卡牌识别依赖感知哈希匹配。旧机制下，首次扫描某系列会下载该系列全部卡图到本地计算哈希（几个 G）。

现在改为：优先从 `shelken/ptcgp-assets` 仓库拉取**预计算好的哈希 JSON**（`hashes/zh-TW/<set>.json`，全量仅约 200KB），解析后批量写入数据库，跳过卡图下载。

仅当某张卡的哈希在 JSON 里缺失时，才回退到下载该张卡图本地计算。

---

## 调度与账号行为

### Q: `init_account` 失败的账号，为什么调度器不再给它派任务？

初始化失败的账号（游戏环境没准备好、卡在新手流程等）如果继续派发日常任务（开包、扫卡等），会在未初始化的游戏界面上空转，陷入无限循环。

调度器会跳过这类账号：只要某账号的 `init_account` 任务处于失败状态、且没有任何成功的 `init_account` 记录，就不向它派发非初始化任务。

这类账号需要排查初始化失败原因后重新触发初始化，恢复后才会重新参与调度。

---

## 更多

- 安装、命令、配置：[README](../../README.md)
- 开发规范、代码结构：[AGENTS.md](../../AGENTS.md)
- 技术参考文档：[docs/refs/](../refs/)
