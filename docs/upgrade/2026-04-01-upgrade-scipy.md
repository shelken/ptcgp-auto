# SciPy 升级核对（2026-04-01）

- 目标版本：`scipy 1.17.0 -> 1.17.1`
- 结论：可以继续升，但这里要说明白，官方站点暂时没看到 `1.17.1` 单独说明页，下面结论是基于补丁版发布形态和项目实际使用范围做的判断。

## 影响范围

- `src/ptcgp_auto_v2/utils/perceptual_hash.py`
  - 只使用 `scipy.fftpack.dct` 做感知哈希计算。
- `yolo-card-training/scripts/test_yolo_hash_match.py`
  - 测试脚本里同样使用 `scipy.fftpack.dct`。

## 变更核对

- `1.17.0`
  - 官方有完整发布说明。
- `1.17.1`
  - 在 PyPI 已确认发布，发布时间是 `2026-02-23`。
  - 官方文档检查时没有找到独立的 `1.17.1` 说明页。
- 当前项目只使用 `fftpack.dct` 这一条稳定接口。
- 这次属于补丁版本升级，没有跨大版本或跨特性分支。

## 备注

- 这里对“低风险”的判断，是基于：
  - 版本跨度仅为补丁级别；
  - 项目实际只打到单一稳定接口；
  - 升级后会直接跑感知哈希冒烟确认。

## 来源

- https://docs.scipy.org/doc/scipy/release.html
- https://docs.scipy.org/doc/scipy/release/1.17.0-notes.html
- https://pypi.org/project/scipy/
