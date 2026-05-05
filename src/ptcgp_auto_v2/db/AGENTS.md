## 数据库规范

- **数据库时间字段统一使用本地时间（localtime）**：
- **v2 数据访问统一规则**：
  - 高层业务动作统一使用 `session_scope()` 作为事务边界
  - 所有 Repository 构造显式传入 `Session`
  - 同一动作需要多个 Repository 时，统一使用 `RepositoryFactory(session)`
  - Repository 内部禁止自建 `Session`、禁止自行 `commit`
  - 模型层禁止 `save()/update()/delete()` 写库入口
  - 事务外只传标量、`dataclass` 纯数据或视图 `dict`
  - 日志、通知、Webhook 等次要副作用放到主数据提交之后单独执行
- **重要**: 所有物理外键 (Foreign Key) 约束已移除；表关系由 SQLAlchemy/SQLModel 逻辑外键 (`Relationship` with `primaryjoin`) 维护
