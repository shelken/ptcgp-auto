# 卡牌预览交互增强设计（记录页 + 拥有页）

## 1. 背景与目标

当前 Web 前端已有卡牌预览能力，但交互体感不稳定，存在“点击后无明显旋转/光效、拖拽失效、状态残留”等回归风险。

本设计目标：
- 抽卡记录页与拥有卡牌页统一为同一套预览内核。
- 点击卡牌后具备明确可感知的进场、旋转、光效与回弹。
- 在不改后端 API/DB 的前提下，仅通过前端实现稳定增强。

## 2. 范围（已锁定）

### 2.1 In Scope
- 抽卡记录页：点击卡牌后进入当前页沉浸预览层，仅查看，不增加业务按钮。
- 拥有卡牌页：点击网格卡后进入现有详情 Modal 左侧预览区，右侧业务区保持不变。
- 统一实现：旋转、拖拽、回弹、进退场翻转、光效分层、主题色光晕、Idle float。
- 统一关闭逻辑：遮罩点击 / ESC / 失焦中断。

### 2.2 Out of Scope
- 不改后端接口。
- 不改数据库模型与数据结构。
- 不引入参考项目源码或素材，仅参考其“分层规则 + 变量驱动”思路。
- 不保留旧预览逻辑并行兼容，采用单路径替换。

## 3. 方案决策

采用“统一预览内核方案（方案 2）”，不走最小修补与视觉优先临时堆叠。

核心原则：
- 简洁优先，单路径执行（Fail-fast）。
- 页面只接线，交互与视觉规则集中到内核模块。
- 动画仅服务进场/退场，落位后由交互内核接管。
- 主题色提取在运行期只允许单引擎，不引入双引擎运行时切换。

## 4. 总体架构

新增并统一以下前端模块职责：

1. `PreviewMotionCore`
- 负责：悬停旋转、拖拽旋转、回弹、指针联动、Idle float 状态切换。
- 输出：统一 CSS 变量（如指针位置、旋转角、光泽强度等）。

2. `PreviewTransitionCore`
- 负责：点击后的进场/退场 FLIP 过渡。
- 约束：只在 entering/leaving 生效，不长期覆盖 `transform`。

3. `PreviewEffectCore`
- 负责：按卡牌元信息匹配光效预设并输出变量/样式类。
- 预设：`basic`、`regular_holo`、`full_art`、`rainbow_secret`、`promo_cosmos`。

4. `PreviewThemeCore`
- 负责：提取卡面主题色并缓存，驱动边框光晕主色。
- 失败回退默认主题色，不阻塞预览链路。

## 5. 页面交互流程与状态机

统一状态机：

`idle -> entering -> active(hover/drag/idle-float) -> leaving -> idle`

### 5.1 抽卡记录页
- 点击缩略图卡牌：从缩略图 FLIP 进场到沉浸预览层。
- 落位后进入 `active`：
  - hover：轻微倾斜 + 光效偏移。
  - drag：更明显倾斜 + 光效增强。
  - idle-float：静置后自然漂浮。
- 关闭：遮罩点击或 ESC，执行退场回落。

### 5.2 拥有卡牌页
- 网格卡点击：从网格卡 FLIP 到详情 Modal 左侧预览位。
- 列表“详情”点击：因缺少缩略图起点，直接在左侧预览位开场（无伪翻转）。
- 右侧业务区保持现状，不改逻辑。

### 5.3 Idle Float（新增硬需求）
- 在 `active` 且无拖拽、指针静止一段时间后，进入 `idle-float` 子状态。
- `idle-float` 触发时延固定为 `1200ms`（指针静止且未按下后开始）。
- `idle-float` 使用 `@keyframes` 进行轻微随机倾斜/位移，模拟自然漂浮。
- 漂浮上限：旋转角 `±2.5deg`，位移 `±2px`，禁止超过该范围。
- 发生指针移动或按下拖拽时，立即退出 `idle-float` 回到实时交互态。
- 关闭或失焦时强制移除 `idle-float` 相关 class，避免残留。

## 6. 光效与主题色规则

### 6.1 光效插件化接口
- 固定接口：`match(meta) -> { vars, styleClass }`。
- 按优先级匹配预设。
- 匹配维度：`rarity + type + set_code + 动态主题色`。

### 6.2 主题色驱动
- 边框光晕始终启用。
- 主色取动态主题色。
- 光晕强度按稀有度分层调整。
- 取色失败时使用默认主题色，不中断预览。

### 6.3 取色引擎决策（固定规则）
- 本次仅做一次性离线评估：对 `fast-average-color` 与 `node-vibrant` 同口径测试后，锁定单一运行时引擎。
- 样本来自本地 `data/ptcgp_v2.db` 的 `cards` 分层抽样，最少 `120` 张。
- 评估脚本放在 `src/ptcgp_auto_v2/web/frontend/scripts/theme-color-benchmark.ts`，在前端目录执行。
- 评估指标：成功率、单张耗时 `P50/P95`、首开额外耗时、包体增量。
- 自动决策规则：
  - 成功率 `< 99%` 直接淘汰。
  - 合格项中优先选 `P95` 更低者。
  - 若 `P95` 差距 `<= 15%`，选包体更小者。
- 结果沉淀到常量配置：仅保留胜出引擎作为运行时实现，不保留运行时切换与后备分支。
- 运行期若取色失败，统一回退默认主题色，不回退到另一取色库。

## 7. 文件边界与改动清单（前端）

### 7.1 主要改动文件
- `src/ptcgp_auto_v2/web/frontend/src/hooks/use-card-preview-drag.ts`
- `src/ptcgp_auto_v2/web/frontend/src/pages/records-page.tsx`
- `src/ptcgp_auto_v2/web/frontend/src/pages/owned-cards-page.tsx`
- `src/ptcgp_auto_v2/web/frontend/src/styles/records-layout.css`
- `src/ptcgp_auto_v2/web/frontend/src/styles/owned-layout.css`

### 7.2 新增/收敛模块
- `src/ptcgp_auto_v2/web/frontend/src/lib/flip-transition.ts`
- `src/ptcgp_auto_v2/web/frontend/src/lib/card-preview-effects.ts`
- `src/ptcgp_auto_v2/web/frontend/src/lib/card-theme-color.ts`
- `src/ptcgp_auto_v2/web/frontend/src/types/node-vibrant-browser.d.ts`

## 8. 错误处理与降级策略

- FLIP 起点/终点信息缺失：跳过过渡，直接进入落位可交互态。
- 取色失败：立即回退默认主题色。
- 关闭、ESC、失焦：统一清理监听器与临时样式。
- `prefers-reduced-motion`：关闭重动画与 Idle float，但保留基本查看与交互。
- 不做旧逻辑兼容分支，不保留双路径。

## 9. 验收标准（主观口径 B）

### 9.1 记录页
- 点击任一卡牌，进场效果肉眼明显。
- 悬停与拖拽时，旋转与光效移动明显可感知。
- 遮罩/ESC 关闭稳定，无错位和残留。

### 9.2 拥有页
- 网格卡点击可进入详情 Modal 左侧预览位。
- 列表“详情”点击可正常打开左侧预览。
- 左侧预览可拖拽旋转并有明显光效。
- 右侧业务区行为不变。

### 9.3 Idle Float
- 静置时可见轻微自然漂浮。
- 交互发生时漂浮立即让位给实时旋转。
- 关闭后再次打开，不继承上次漂浮状态。

### 9.4 稳定性
- 连续打开/关闭、多页面切换不出现“不可拖拽/无动画/无光效”回归。
- 在 `src/ptcgp_auto_v2/web/frontend` 目录执行 `bun run build` 通过。
- 在仓库根目录执行 `uv run ruff check src` 通过。

## 10. 参考资料

- https://github.com/simeydotme/pokemon-cards-css
- https://github.com/simeydotme/pokemon-cards-css/blob/main/src/lib/components/Card.svelte
- https://github.com/simeydotme/pokemon-cards-css/blob/main/public/css/cards/base.css
- https://www.npmjs.com/package/fast-average-color
- https://www.npmjs.com/package/node-vibrant
