# 依赖升级基线与流程（2026-04-01）

## 当前依赖管理边界

- Python 主项目：`pyproject.toml` + `uv.lock`
- 前端项目：`src/ptcgp_auto_v2/web/frontend/package.json` + `bun.lock`
- Python 训练子项目：`yolo-card-training/pyproject.toml` + `yolo-card-training/uv.lock`
- 当前工具版本：
  - `uv 0.11.2`
  - `bun 1.3.11`

## 现状结论

- Python 主项目已经有锁文件，适合做“单包升级 -> 验证 -> 提交”。
- 前端项目也有锁文件，适合做“单包或小批量升级 -> 类型检查/构建 -> 提交”。
- 已确认并移除 Python 主项目中的历史残留依赖：`jinja2`、`python-multipart`、`questionary`。
- `pyproject.toml` 里声明了 `pytest` 路径，但仓库当前没有对应的 `src/ptcgp_auto_v2/tests` 和 `src/ptcgp_auto_v2/web/tests` 目录。
- 这意味着关键依赖升级时，当前不能把“跑 pytest”当成主要兜底，仍要依赖 lint、typecheck、build、Web 冒烟和任务冒烟。

## 关键依赖

### Python 关键依赖

- `fastapi`
  - Web 入口和全部 API 路由都直接依赖。
- `uvicorn`
  - Web 启动链路直接依赖。
- `sqlmodel`
  - v2 数据模型、仓储、查询层全面依赖。
- `uiautomator2`
  - ADB / UI 自动化核心链路直接依赖。
- `numpy`
  - 图像识别、哈希、颜色计算、YOLO 相关链路广泛依赖。
- `opencv-python`
  - 图像识别核心链路直接依赖。
- `pillow`
  - 截图、图像转换、工具链广泛依赖。
- `scipy`
  - 感知哈希核心计算直接依赖。
- `ultralytics`
  - YOLO 模型加载和识别链路直接依赖。
- `coremltools`
  - 模型导出和 CoreML 相关能力直接依赖。
- `pyobjc-framework-vision`
  - macOS Vision OCR 能力直接依赖。

### 前端关键依赖

- `react`
  - 全部页面和组件根基。
- `react-dom`
  - 前端挂载入口根基。
- `react-router-dom`
  - 页面路由和 URL 状态依赖。
- `@tanstack/react-query`
  - 页面数据获取和缓存根基。
- `typescript`
  - 前端类型检查根基。
- `vite`
  - 前端构建和开发入口根基。
- `tailwindcss`
  - 样式构建根基。
- `@vitejs/plugin-react-swc`
  - React 编译链路关键插件。

## 非关键依赖

### Python 非关键依赖

- `loguru`
- `pytest`
- `vulture`

### 前端非关键依赖

- `@radix-ui/react-select`
- `@radix-ui/react-slot`
- `class-variance-authority`
- `clsx`
- `dompurify`
- `fast-average-color`
- `lucide-react`
- `marked`
- `node-vibrant`
- `tailwind-merge`
- `@types/node`
- `@types/react`
- `@types/react-dom`
- `autoprefixer`
- `postcss`
- `tailwindcss-animate`
- `knip`

## Python 主项目当前可升级项快照

基于 `uv tree --outdated --depth 1`：

- `fastapi`：`0.128.0 -> 0.135.2`
- `numpy`：`2.3.5 -> 2.4.4`
- `opencv-python`：`4.13.0.90 -> 4.13.0.92`
- `pillow`：`12.1.0 -> 12.1.1`
- `scipy`：`1.17.0 -> 1.17.1`
- `sqlmodel`：`0.0.31 -> 0.0.37`
- `ultralytics`：`8.4.10 -> 8.4.33`
- `uvicorn`：`0.40.0 -> 0.42.0`
- `vulture`：`2.15 -> 2.16`

## 依赖变更流程

### 1. 先盘点，不直接升级

- Python：
  - `uv tree --outdated --depth 1`
- 前端：
  - `bun outdated`

### 2. 先分组

- 关键依赖：一次只升一个，最多同生态一小组。
- 非关键依赖：可以按批次直接升到最新。

### 3. 关键依赖升级规则

- 先看官方发布说明 / 迁移说明 / 破坏性变更。
- 只升级一个关键依赖，避免混在一起定位不清。
- Python 用：
  - `uv lock --upgrade-package <pkg>`
  - 如果要调整声明范围，再用 `uv add '<pkg spec>'`
- 前端用：
  - `bun update <pkg> --latest`

### 4. 关键依赖验证规则

- Python Web / 数据链路相关依赖：
  - `uv run ruff check src main.py main_v2.py debug_tool.py scripts yolo-card-training/scripts`
  - `uv run vulture`
  - 启动 Web 做一次页面冒烟
- Python 自动化 / 图像识别相关依赖：
  - 相关调试脚本冒烟
  - 必要时跑一次单任务调试
- 前端关键依赖：
  - `bun run typecheck`
  - `bun run build`
  - Web 页面冒烟
- 当前自动测试覆盖不足时：
  - 先补最小必要测试，再升级关键依赖

### 5. 非关键依赖升级规则

- Python：
  - 同批次升级非关键依赖后，统一跑 lint / 死代码检查
- 前端：
  - 同批次升级非关键依赖后，统一跑 `typecheck` / `build`

### 6. 提交规则

- 一个提交只做一类事：
  - 一个关键依赖
  - 或一批非关键依赖
  - 或流程文档 / 工具脚本
- 提交信息写明：
  - 升了什么
  - 是否涉及重大变更
  - 跑了哪些验证

## 推荐执行顺序

1. 先处理非关键依赖
2. 再处理 Web 关键依赖：`fastapi`、`uvicorn`、`sqlmodel`
3. 再处理前端关键依赖：`vite`、`typescript`、`react` 生态
4. 最后处理自动化 / 图像识别关键依赖：`numpy`、`opencv-python`、`scipy`、`ultralytics`、`coremltools`

## 来源

- `uv` CLI 参考：<https://docs.astral.sh/uv/reference/cli/>
- `uv` 锁定与同步：<https://docs.astral.sh/uv/concepts/projects/sync/>
- `bun update`：<https://github.com/oven-sh/bun/blob/main/docs/pm/cli/update.mdx>
- `bun outdated`：<https://github.com/oven-sh/bun/blob/main/docs/guides/install/from-npm-install-to-bun-install.mdx>
