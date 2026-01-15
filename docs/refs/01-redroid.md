# Redroid

GPU 加速的 Android 容器方案，专为云端/服务器多实例设计。

## 关键信息

- **GitHub**: https://github.com/remote-android/redroid-doc
- **架构**: arm64 / amd64
- **Android**: 8.1 - 16

## 系统要求

需要 Linux 内核模块：`binder_linux`、`ashmem_linux`。详见 [05-redroid-kernel-modules.md](05-redroid-kernel-modules.md)。

## 快速开始

```bash
docker run -itd --privileged -v ~/data:/data -p 5555:5555 redroid/redroid:12.0.0_64only-latest
adb connect localhost:5555
```

## 配置

通过启动参数配置分辨率、DPI、GPU 模式等。详见官方文档：https://github.com/remote-android/redroid-doc#configuration

## macOS 使用

需要通过 Linux VM 或远程服务器运行，详见 [04-lima-vm.md](04-lima-vm.md) 和 [06-cloud-redroid-deployment.md](06-cloud-redroid-deployment.md)。

## 本地 Lima (macOS M3)

在 macOS M3 上推荐通过 Lima 启动 Linux VM，然后运行 Redroid 容器：

```bash
docker run -itd --privileged -v ~/data:/data -p 15555:15555 redroid/redroid:13.0.0_64only-latest
adb connect localhost:15555
```

默认将 Redroid 的 ADB 端口映射到宿主机的 15555，**请不要将该端口暴露到公共网络**，只在受控网络或本地环境使用。
