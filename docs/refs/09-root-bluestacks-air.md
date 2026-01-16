# Root BlueStacks Air macOS

> 来源：https://github.com/hanreev/root-bluestacks-air

## 核心原理

该项目通过修改 BlueStacks Air 的 **initrd（初始化内存盘）镜像** 来注入 Magisk，实现 root 权限。

**关键点**：root 的是 **BlueStacks Air 应用本身**（即底层的 Android 虚拟机），而不是单独的模拟器实例。

---

## Root 流程详解

### 1. 修改目标

```
/Applications/BlueStacks.app/Contents/img/initrd_hvf.img
```

这是 BlueStacks 的 **初始化 RAM 磁盘镜像**，在 Android 系统启动时被加载。修改此文件会影响 **所有** 使用该 BlueStacks 安装的模拟器实例。

### 2. 技术步骤

#### 步骤 1：解压 Magisk APK

```bash
unzip -oq magisk.apk -d magisk
```

从 Kitsune Magisk APK 中提取：
- `magisk64` - Magisk 主程序
- `magiskinit` - Magisk 初始化程序
- `magiskpolicy` - SELinux 策略修改器
- `stub.apk` - Magisk 存根

#### 步骤 2：解包 initrd

```bash
cat initrd_hvf.img | cpio -id
```

initrd 是一个 cpio 归档文件，解压后得到 Android 启动所需的基础文件系统。

#### 步骤 3：注入 Magisk 文件

```bash
cp -r magisk-bin boot/magisk
cp magisk.rc boot/magisk.rc
```

将 Magisk 二进制文件复制到 `boot/magisk/` 目录。

#### 步骤 4：修改启动脚本

修改 `boot/stage2.sh`，在 `exec /init` 之前注入：

```bash
log_echo "Installing magisk.rc"
cat /boot/magisk.rc >> /init.bst.rc
exec /init
```

这会将 Magisk 的 rc 配置追加到 BlueStacks 的初始化脚本中。

#### 步骤 5：重新打包 initrd

```bash
find . | cpio -H newc -o | gzip > initrd_hvf.img
```

#### 步骤 6：替换原始 initrd

将打补丁的 `initrd_hvf.img` 复制回：
```
/Applications/BlueStacks.app/Contents/img/initrd_hvf.img
```

### 3. Magisk 启动流程（magisk.rc）

```
on post-fs-data
    # 修改 SELinux 策略
    exec magiskpolicy --live --magisk
    # 设置 Magisk 到 /sbin
    exec magisk64 --auto-selinux --setup-sbin /boot/magisk /sbin
    # 执行 post-fs-data 阶段
    exec /sbin/magisk --auto-selinux --post-fs-data

on property:sys.boot_completed=1
    # 启动完成后创建 Magisk 数据目录
    mkdir /data/adb/magisk 755
    exec /sbin/magisk --auto-selinux --boot-complete
```

---

## 关键问题解答

### Q1: Root 的是 BlueStacks Air 本身还是其中的模拟器？

**答：Root 的是 BlueStacks Air 应用本身。**

技术上说，修改的是 `/Applications/BlueStacks.app/Contents/img/initrd_hvf.img`，这个文件是 BlueStacks 应用的一部分，被所有模拟器实例共享。

### Q2: 是否需要对每个模拟器都执行 root？

**答：不需要。**

只需执行一次 root 操作，修改 `initrd_hvf.img` 后，**所有现有和新创建的模拟器实例都会自动获得 root 权限**。

### Q4: 现有模拟器需要删除重建吗？

**答：不需要删除。**

Root 修改的是 BlueStacks **应用级别** 的启动镜像 `initrd_hvf.img`，这个文件在 **每次模拟器启动时** 都会被加载。因此：

- ✅ 现有模拟器只需 **重启** 即可自动获得 root
- ✅ 不需要删除或重建任何 VM 实例

**现有模拟器启用 root 的步骤**：

```
1. 执行 root.sh 修改 initrd_hvf.img
2. 重启现有模拟器
3. 安装 Kitsune Magisk APK（每个实例一次）
4. 完成 Magisk 的 Additional Setup（每个实例一次）
5. 完成，该实例现在拥有 root 权限
```

**注意**：如果使用模板复制方式创建新实例，连 Magisk 安装步骤也可省略（Magisk 配置已在 `data.qcow2` 中）。

| 场景 | 是否需要删除现有 VM |
|------|---------------------|
| 执行 root.sh 后 | ❌ 不需要，重启即生效 |
| 想用模板批量创建 | ❌ 不需要，直接复制 VM 文件 |
| BlueStacks 升级后 | ⚠️ 可能需要重新执行 root.sh（initrd 可能被覆盖） |

### Q3: 可以配置模板 root 后直接拷贝吗？

**答：可以，但需要注意以下几点：**

1. **initrd 是全局的**：root 修改的是 BlueStacks 应用级别的文件，不是单个 VM 的数据
2. **VM 数据独立**：每个模拟器实例的数据（`data.qcow2`）是独立的
3. **Magisk 数据持久化**：首次启动 Magisk 会在 `/data/adb/magisk` 创建数据

**推荐工作流程**：
```
1. 执行一次 root（修改 initrd_hvf.img）
2. 创建一个"模板"模拟器实例
3. 安装 Kitsune Magisk 并完成设置
4. 复制该实例的 VM 文件作为模板
   - 位置：/Users/Shared/Library/Application Support/BlueStacks/vms/Tiramisu64_X/
5. 新实例直接复制模板 VM 文件即可
```

---

## 两种 Root 方法对比

| 方法 | SIP 状态 | 操作方式 | 优点 | 缺点 |
|------|----------|----------|------|------|
| Method 1 | 启用 | 手动复制 initrd | 不需要禁用 SIP | 需要手动替换文件 |
| Method 2 | 禁用 | sudo 自动替换 | 全自动 | 需要禁用 SIP |

### Method 1（推荐，SIP 启用）

```bash
# 生成打补丁的 initrd 到自定义位置
bash root.sh -o files/initrd_hvf.img -b files/backup

# 手动复制到 BlueStacks
cp files/initrd_hvf.img /Applications/BlueStacks.app/Contents/img/
```

### Method 2（SIP 禁用）

```bash
sudo bash root.sh
```

---

## 依赖要求

- **BlueStacks Air**: macOS 版本
- **Kitsune Magisk**: [v27.2-kitsune-4](https://github.com/1q23lyc45/KitsuneMagisk/releases) 或更新版本

### 已测试版本

- 5.21.680.7532 ~ 5.21.745.7536

---

## 后续步骤

1. 安装 `magisk.apk`（Kitsune Magisk）
2. 打开 Kitsune Mask，完成 **Requires Additional Setup**
3. 如需 **Zygisk**，在设置中启用并重启
4. 可选：安装 LSPosed 等模块

---

## Unroot 方法

### SIP 启用

```bash
# 恢复备份的 initrd
cp files/backup/initrd_hvf.img /Applications/BlueStacks.app/Contents/img/
```

### SIP 禁用

```bash
sudo bash unroot.sh
```

---

## 程序中检测 Root 状态

在 ADB 连接设备后，可通过以下方式检测是否拥有 root 权限：

### 命令行检测

```bash
# 尝试执行 su 命令
adb -s 127.0.0.1:5555 shell "su -c 'id'"
# 成功返回 uid=0(root) → 已 root
# 返回错误或超时 → 未 root
```

### Python 快速检测

```python
import subprocess

def is_rooted(device_address: str) -> bool:
    """检查设备是否已 root"""
    try:
        result = subprocess.run(
            ["adb", "-s", device_address, "shell", "su", "-c", "echo 1"],
            capture_output=True,
            text=True,
            timeout=3
        )
        return result.stdout.strip() == "1"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False

# 使用示例
if is_rooted("127.0.0.1:5555"):
    print("设备已 root")
else:
    print("设备未 root 或 Magisk 未完成设置")
```

**注意**：如果 Magisk 还没完成 Additional Setup，即使已执行 root.sh，`su` 命令也可能不可用。

---

## 与账号管理的关系

Root 后可以通过 ADB shell 获取 `su` 权限，从而：
- 访问 `/data/data/` 目录
- 提取/注入 `deviceAccount:.xml` 进行账号切换
- 参见 `08-ptcgpb-xml-account-management.md`
