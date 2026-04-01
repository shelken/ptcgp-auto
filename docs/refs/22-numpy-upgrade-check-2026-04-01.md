# NumPy 升级核对（2026-04-01）

- 目标版本：`numpy 2.3.5 -> 2.4.4`
- 结论：可以继续升，但这是关键共享依赖，主项目和训练子项目必须一起调整。

## 影响范围

- `pyproject.toml`
  - 主项目当前手工限制为 `numpy>=1.14.5,<=2.3.5`。
- `yolo-card-training/pyproject.toml`
  - 训练子项目也写了同样的上限。
- `src/ptcgp_auto_v2/utils/perceptual_hash.py`
  - 使用 `np.array()`、`np.sqrt()`、`np.mean()`、`np.ceil()`、`np.uint32`。
- `src/ptcgp_auto_v2/infra/template.py`
  - 使用 `np.array()` 做图像转换。
- `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py`
  - 使用 NumPy 数组和与 OpenCV、YOLO 的数据交换。
- `yolo-card-training/scripts/test_yolo_hash_match.py`
  - 使用 NumPy + SciPy 的哈希计算链路。

## 兼容性核对

- 当前已装依赖元数据里，没有看到把 NumPy 锁死在 `2.3.5`：
  - `coremltools 9.0`：`numpy>=1.14.5`
  - `opencv-python 4.13.0.92`：Python 3.9+ 使用 `numpy>=2`
  - `scipy 1.17.1`：`numpy>=1.26.4,<2.7`
  - `ultralytics 8.4.10`：`numpy>=1.23.0`
- 这说明 `<=2.3.5` 更像项目自己的历史上限，不是当前外部依赖硬约束。

## 官方变更核对

- 官方有 `2.4.0` 变更说明。
- `2.4.1`、`2.4.4` 没找到单独的说明页，本次按 `2.4.x` 系列补丁版处理。
- 已扫过仓库，暂时没看到明显踩到 `2.4.0` 里高风险旧用法的地方，比如：
  - `np.in1d`
  - 旧的 `quantile(..., interpolation=...)`
  - 依赖已废弃内部模块路径

## 验证策略

- 主项目：
  - `ruff`
  - `vulture`
  - 导入 `coremltools`、`cv2`、`scipy`、`ultralytics`
  - 跑感知哈希和图像转换冒烟
- 训练子项目：
  - 导入 `numpy`、`cv2`、`coremltools`、`ultralytics`
  - 跑哈希相关最小冒烟

## 来源

- https://numpy.org/doc/stable/release/2.4.0-notes.html
- https://pypi.org/project/numpy/
