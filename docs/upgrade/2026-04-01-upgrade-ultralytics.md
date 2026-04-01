# Ultralytics 升级核对（2026-04-01）

- 目标版本：`ultralytics 8.4.10 -> 8.4.33`
- 结论：可以继续升，当前公开可见的这段版本更新主要集中在导出、平台和训练侧修复。

## 影响范围

- `src/ptcgp_auto_v2/infra/model_manager.py`
  - 主项目会直接执行 `YOLO(model_path, task="obb")`。
- `yolo-card-training/scripts/train.py`
  - 训练项目直接用 `YOLO("yolo11n-obb.pt")` 和本地权重继续训练。
- `yolo-card-training/scripts/test_model.py`
  - 测试脚本直接加载本地模型。
- `yolo-card-training/scripts/test_yolo_hash_match.py`
  - 测试脚本直接创建 `YOLO(model_path)`。

## 官方信息核对

- PyPI 已确认 `8.4.33` 发布时间为 `2026-03-31T17:08:52Z`。
- 同一段版本公开 release 标题里，`8.4.24` 到 `8.4.32` 主要是训练、导出、平台兼容和设备支持修复。
- 当前 `8.4.33` 的依赖要求仍兼容我们现在的：
  - `numpy>=1.23.0`
  - `opencv-python>=4.6.0`
  - `pillow>=7.1.2`
  - `scipy>=1.4.1`
  - `torch>=1.8.0`

## 验证策略

- 主项目环境：
  - 导入 `YOLO`
  - 用现有 `best.mlpackage` 创建 `YOLO(..., task="obb")`
- 训练子项目环境：
  - 导入 `YOLO`
  - 读取当前版本号

## 来源

- https://pypi.org/project/ultralytics/8.4.33/
- https://github.com/ultralytics/ultralytics/releases
