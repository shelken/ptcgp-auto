# Android 容器化方案 - 总览

## 核心结论

**所有 Android 容器方案都需要 Linux 内核，macOS 无法直接运行。**

## 方案对比

| 方案 | 状态 | 多实例 | 链接 |
|------|------|--------|------|
| Redroid | ✅ 活跃 | ✅ 优秀 | [01-redroid.md](01-redroid.md) |
| Waydroid | ✅ 活跃 | ❌ 有限 | [02-waydroid.md](02-waydroid.md) |
| Anbox | ❌ 废弃 | - | [03-anbox.md](03-anbox.md) |

## macOS 可行路径

| 方案 | 难度 | 费用 | 详情 |
|------|------|------|------|
| 本地 Lima VM | 高 | 免费 | [04-lima-vm.md](04-lima-vm.md) |
| 云服务器 | 中 | 低 | [06-cloud-redroid-deployment.md](06-cloud-redroid-deployment.md) |

## 其他参考

- 内核模块安装：[05-redroid-kernel-modules.md](05-redroid-kernel-modules.md)
- 检测与伪装：[07-detection-bypass.md](07-detection-bypass.md)

## 推荐路径

1. 先在 Lima VM 中测试 Redroid 可行性
2. 测试 PTCGP 能否运行
3. 如果可行，考虑云端部署扩展
