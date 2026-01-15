# Lima 虚拟机

在 macOS 上运行 Linux VM，可用于运行 Redroid。

## 关键信息

- **官网**: https://lima-vm.io
- **GitHub**: https://github.com/lima-vm/lima

## 安装

```bash
brew install lima
limactl start
```

## 虚拟机类型

- `vz`：Apple 原生虚拟化，macOS 13.5+，最佳性能
- `qemu`：软件模拟，兼容性更好

## Redroid 配置示例

```yaml
# lima-redroid.yaml
vmType: vz
arch: aarch64
cpus: 4
memory: 8GiB

provision:
  - mode: system
    script: |
      apt-get update && apt-get install -y linux-modules-extra-$(uname -r)
      modprobe binder_linux devices="binder,hwbinder,vndbinder"

portForwards:
  - guestPort: 5555
    hostPort: 5555
```

## 挑战

标准 Ubuntu 云镜像可能没有 binder/ashmem 模块，需要自定义内核或安装模块。

## 参考

- 文档: https://lima-vm.io/docs/
- 模板: https://github.com/lima-vm/lima/tree/master/templates
