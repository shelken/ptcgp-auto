# Android 检测与伪装

游戏可能检测容器/模拟器环境。

## 检测类型

| 类型 | Redroid 默认状态 |
|------|------------------|
| Play Integrity | ❌ 不通过 |
| Root 检测 | ❌ 被检测（默认 root）|
| 设备指纹 | ❌ 显示为 "redroid" |
| 模拟器检测 | ⚠️ 取决于具体检查 |

## 伪装方法

通过启动参数覆盖设备属性：

```bash
docker run ... redroid/redroid:12.0.0_64only-latest \
    ro.product.model=Pixel_6 \
    ro.product.manufacturer=Google
```

## PTCGP 状态

BlueStacks 可运行，说明检测不是最严格的。需要实际测试 Redroid 是否可行。

## 参考

- Redroid Issues: https://github.com/remote-android/redroid-doc/issues
- Play Integrity: https://developer.android.com/google/play/integrity
