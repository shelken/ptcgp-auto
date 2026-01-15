# 云服务器 Redroid 部署

在云 Linux 服务器上部署 Redroid，通过网络 ADB 控制。

## 推荐服务商

| 服务商 | 类型 | 费用 |
|--------|------|------|
| Oracle Cloud A1.Flex | ARM | 免费层 |
| Hetzner CAX11 | ARM | ~€4/月 |
| AWS t4g.medium | ARM | ~$22/月 |

## 快速部署 (Ubuntu 22.04)

```bash
# 安装模块和 Docker
sudo apt install linux-modules-extra-$(uname -r)
sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"
curl -fsSL https://get.docker.com | sh

# 运行 Redroid
docker run -itd --privileged -v ~/data:/data -p 5555:5555 redroid/redroid:12.0.0_64only-latest
```

## 连接

```bash
# 本地通过 SSH 隧道连接（安全）
ssh -L 5555:localhost:5555 user@server
adb connect localhost:5555
```

## 多实例

使用 Docker Compose 或循环创建多个容器，每个用不同端口。

## 参考

- 部署文档: https://github.com/remote-android/redroid-doc/tree/master/deploy
- Oracle 免费层: https://www.oracle.com/cloud/free/
