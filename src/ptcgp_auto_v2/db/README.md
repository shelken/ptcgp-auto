# 数据库模块说明

本模块使用 **SQLModel** 作为 ORM 层

## 目录结构

```
db/
├── __init__.py          # 模块导出
├── engine.py            # 数据库引擎和会话管理
├── connection.py        # 旧的连接模块（仅用于初始化 schema）
├── repositories/        # 数据访问层（Repository 模式）
│   ├── __init__.py
│   ├── account_repository.py
│   ├── account_stat_repository.py
│   └── ...
├── models/              # SQLModel 模型定义
│   ├── __init__.py
│   ├── base.py          # 基础类和 Mixin
│   ├── account.py
│   ├── account_stat.py
│   ├── account_pack_config.py
│   ├── pack_record.py
│   ├── task_instance.py
│   └── task_plan.py

```

## 当前访问规则

- 默认的高层动作边界使用 `session_scope()`
- 同一高层动作需要多个 Repository 时，统一通过 `RepositoryFactory(session)` 组装
- 所有 Repository 构造都必须显式传入 `session`
- Repository 方法内部禁止再写 `Session(get_engine())` 或 `with Session(...)`
- Repository 写入统一通过 `_finish_write()` 完成；当前行为是 `flush + refresh`
- Repository 不拥有事务边界，也不负责创建和关闭 Session
- 禁止模型对象自己 new Repository 并持久化；模型层只表达数据
- `TaskInstance.save()` 等模型层写库入口已删除
- `get_session()` / `get_fastapi_session()` 使用 SQLAlchemy 默认的提交后过期语义
- `session_scope()` 正常退出时统一 `commit()`，异常时 `rollback()`
- 需要跨事务传递的数据，必须先投影成 `dataclass` 纯数据或标量；不要把 ORM 实体带出 `session_scope()`
- 通用投影逻辑统一复用 `BaseRepository._to_data()`，不要在各个 Repository 重复写 `from_model`
