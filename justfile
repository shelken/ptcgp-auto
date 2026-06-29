# 扫描 git 历史, 限定标准 ref 命名空间, 排除 AI agent 检查点 ref
scan:
    betterleaks git --log-opts "--branches --tags --remotes"

# 扫描工作区文件(含未跟踪文件,可发现 .env 等未进库但本地的密钥)
scan-dir:
    betterleaks dir .

# 详细模式: 打印每条 finding 的 rule/path/secret, 用于排查误报
scan-verbose:
    betterleaks git --log-opts "--branches --tags --remotes" -v
