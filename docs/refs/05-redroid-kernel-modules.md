# Redroid 内核模块

Redroid 需要 `binder_linux` 和 `ashmem_linux` 内核模块。

## Ubuntu 20.04+ (内核 5.0+)

```bash
sudo apt install linux-modules-extra-$(uname -r)
sudo modprobe binder_linux devices=binder,hwbinder,vndbinder
sudo modprobe ashmem_linux
```

## 验证

```bash
lsmod | grep -e ashmem -e binder
```

如果使用 Ubuntu 24.04，部分内核模块可能尚未包含在默认镜像中，此时可在目标系统内执行 `modprobe binder_linux` 和 `modprobe ashmem_linux` 后，再用上述命令确认加载情况。

## 其他发行版

详见官方文档：https://github.com/remote-android/redroid-modules

## 自定义内核

启用以下配置：
- `CONFIG_ANDROID_BINDER_IPC=y`
- `CONFIG_ANDROID_BINDERFS=y`
- `CONFIG_ASHMEM=y`
