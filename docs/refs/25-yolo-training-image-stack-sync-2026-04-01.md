# 训练子项目图像栈同步（2026-04-01）

- 目标：把 `yolo-card-training` 中的 `opencv-python`、`pillow`、`scipy` 同步到和主项目一致的已验证版本。

## 同步版本

- `opencv-python 4.13.0.90 -> 4.13.0.92`
- `pillow 12.1.0 -> 12.1.1`
- `scipy 1.17.0 -> 1.17.1`

## 原因

- 这三项在主项目里已经完成过真实链路验证：
  - 图像读写、裁剪、缩放
  - OpenCV 颜色转换
  - SciPy DCT 感知哈希
- 训练子项目同样依赖这套图像处理能力。
- 继续保留两边不同版本，只会增加后续排查成本。

## 验证策略

- 训练子项目环境导入：
  - `cv2`
  - `PIL`
  - `scipy`
  - `ultralytics`
- 运行 NumPy + SciPy DCT 最小冒烟

## 来源

- 主项目已通过的升级核对：
  - `/Users/shelken/Code/active/ptcgp-auto/docs/refs/19-pillow-upgrade-check-2026-04-01.md`
  - `/Users/shelken/Code/active/ptcgp-auto/docs/refs/20-scipy-upgrade-check-2026-04-01.md`
  - `/Users/shelken/Code/active/ptcgp-auto/docs/refs/21-opencv-python-upgrade-check-2026-04-01.md`
