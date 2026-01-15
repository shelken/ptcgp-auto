# Redroid + Lima 可行性测试设计

## 背景

需要在 macOS M3 上验证 Redroid 是否可用，并能安装与启动 PTCGP。由于 macOS 无法直接运行 Redroid，需要使用 Lima 提供 Linux VM。

## 目标

- 在本地 Lima VM 内运行 Redroid Android 容器
- 宿主机可通过 `adb` 连接
- 能安装并启动 PTCGP（主界面）

## 成功标准

- `adb connect 127.0.0.1:15555` 连接成功
- `adb install` 安装 APK 成功
- `adb shell am start ...` 能启动 PTCGP 主界面

## 设计方案

### 方案选型

**本地 Lima VM + Redroid 官方镜像**

- 使用 Lima 创建专用 Ubuntu 24.04 VM（ARM64）
- VM 内加载 `binder_linux` / `ashmem_linux` 内核模块
- 运行 Redroid 官方镜像 `redroid/redroid:13.0.0_64only-latest`
- 端口映射 `guest 5555 -> host 15555`，避免 BlueStacks 冲突

优点：
- 完全本地验证，无需云端依赖
- 操作路径清晰，可复用

缺点：
- 依赖内核模块，Ubuntu 24.04 可能缺模块
- 性能与稳定性未验证

### 架构与组件

- **宿主机（macOS）**：执行 adb、管理 Lima
- **Lima VM**：提供 Linux 内核与 Docker 环境
- **Redroid 容器**：运行 Android 13

数据流：
- `adb`（宿主机）→ Lima 端口转发 → Redroid adb 服务
- APK 从 BlueStacks 提取后经 `adb install` 安装

## 实施步骤

1. 新建 `lima-redroid.yaml`（专用配置，不复用现有 BlueStacks 清理 VM）
   - `vmType: vz`
   - `arch: aarch64`
   - `cpus: 4`
   - `memory: 8GiB`
   - `provision`：安装模块与 Docker
2. VM 内安装与加载模块
   - `apt-get install -y linux-modules-extra-$(uname -r)`
   - `modprobe binder_linux devices="binder,hwbinder,vndbinder"`
   - `modprobe ashmem_linux`
3. 启动 Redroid 容器
   - `docker run -itd --privileged -v ~/data:/data -p 15555:5555 redroid/redroid:13.0.0_64only-latest`
4. 宿主机连接 adb
   - `adb connect 127.0.0.1:15555`
   - `adb devices`
5. 安装并启动 PTCGP
   - 从 BlueStacks 提取 APK
   - `adb install ./PTCGP.apk`
   - `adb shell am start ...`

## 验证清单

- VM 正常启动
- `lsmod` 可看到 binder/ashmem
- Redroid 容器运行中
- `adb devices` 显示设备
- PTCGP 可启动

## 风险与边界

- Ubuntu 24.04 可能缺少 `binder/ashmem` 模块，需要根据错误信息决定是否降级到 22.04 或使用 redroid-modules
- 仅验证可行性，不保证性能、GPU 加速或多实例能力
- 不涉及 GMS、WebRTC 等扩展功能

## 参考资料

- https://github.com/remote-android/redroid-doc
- `docs/refs/01-redroid.md`
- `docs/refs/04-lima-vm.md`
- `docs/refs/05-redroid-kernel-modules.md`
