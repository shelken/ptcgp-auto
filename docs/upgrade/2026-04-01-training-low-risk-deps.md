# 训练子项目低风险依赖升级（2026-04-01）

- 目标：
  - `requests 2.32.5 -> 2.33.1`
  - `tqdm 4.67.1 -> 4.67.3`

## 结论

- 这两项只影响训练脚本里的下载、进度显示和命令行体验。
- 不涉及模型结构、图像处理、数据库或 Web 链路。
- 适合按低风险依赖批量升级。

## 验证策略

- 训练子项目环境导入：
  - `requests`
  - `tqdm`
  - `ultralytics`

## 来源

- https://pypi.org/project/requests/
- https://pypi.org/project/tqdm/
