# Pillow 升级核对（2026-04-01）

- 目标版本：`pillow 12.1.0 -> 12.1.1`
- 结论：可以直接升，当前主要是安全修复，没看到会打到本项目已使用接口的破坏性改动。

## 影响范围

- `src/ptcgp_auto_v2/utils/perceptual_hash.py`
  - 使用 `Image.open()`、`convert()`、`resize()`、`Image.Resampling.BICUBIC`。
- `src/ptcgp_auto_v2/utils/pack_image_manager.py`
  - 使用 `Image.open()`、`save()`、裁剪、模式转换。
- `src/ptcgp_auto_v2/infra/*`、`src/ptcgp_auto_v2/tools/*`
  - 广泛依赖 `PIL.Image` 做截图、裁剪、颜色转换和模板处理。

## 变更核对

- `12.1.1`
  - 主要是一个 PSD 解析相关的安全修复。
  - 另外有一个和 `libavif` 构建兼容性相关的修补。
- 当前项目核心用法是基础图片读写、裁剪、缩放、颜色模式转换。
- 当前项目没有直接处理 PSD 文件，也没有依赖这次说明里提到的新废弃接口。

## 来源

- https://pillow.readthedocs.io/en/stable/releasenotes/index.html
- https://pillow.readthedocs.io/en/stable/releasenotes/12.1.1.html
- https://pillow.readthedocs.io/en/stable/releasenotes/12.1.0.html
