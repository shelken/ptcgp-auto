# opencv-python 升级核对（2026-04-01）

- 目标版本：`opencv-python 4.13.0.90 -> 4.13.0.92`
- 结论：可以直接升。这是同一主版本下的补丁发布，公开说明里主要提到 X server 依赖修复。

## 影响范围

- `src/ptcgp_auto_v2/infra/template.py`
  - 使用 `cv2.imread()`、`resize()`、`cvtColor()`、`matchTemplate()`。
- `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py`
  - 使用颜色空间转换、透视变换、裁剪。
- `src/ptcgp_auto_v2/utils/perceptual_hash.py`
  - 使用 `cvtColor()`、`resize()`。
- `src/ptcgp_auto_v2/utils/color.py`
  - 使用 `cvtColor()`、`inRange()`。

## 变更核对

- `4.13.0.92`
  - `opencv-python` 仓库公开说明里写的是 `4.13.0` 的后续补丁，修了 X server 依赖问题。
- 当前项目运行环境是 macOS，本地主要依赖 OpenCV 的基础图像处理接口。
- 当前项目没有依赖这次说明里提到的 Linux/X server 安装行为。

## 来源

- https://github.com/opencv/opencv-python/releases
- https://pypi.org/project/opencv-python/
