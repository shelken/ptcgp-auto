# PTCGP Auto V2 测试指南

v2 代码库的所有测试都必须位于此目录 (`src/ptcgp_auto_v2/tests/`) 下，并严格镜像源代码的目录结构。

## 目录结构

*   `core/`: 测试 `src/ptcgp_auto_v2/core/` (Scheduler, Executor, TaskBase)
*   `tasks/`: 测试 `src/ptcgp_auto_v2/tasks/` (具体任务实现)
*   `db/`: 测试 `src/ptcgp_auto_v2/db/` (Repositories, Models)
*   `infra/`: 测试 `src/ptcgp_auto_v2/infra/` (ADB, OCR, Device management)

## 测试规范

1.  **镜像结构**：如果你要测试 `src/ptcgp_auto_v2/db/repositories.py`，测试文件应位于 `src/ptcgp_auto_v2/tests/db/test_repositories.py`。
2.  **命名规则**：所有测试文件必须以 `test_` 开头。
3.  **测试类型**：
    *   **单元测试 (Unit Tests)**：Mock 外部依赖（DB, ADB 等），隔离测试逻辑。
    *   **集成测试 (Integration Tests)**：测试与 SQLite 的交互（请使用内存数据库 `sqlite:///:memory:` 或临时文件）。
4.  **运行测试**：
    在项目根目录下运行所有 v2 测试：
    ```bash
    pytest src/ptcgp_auto_v2/tests/
    ```
