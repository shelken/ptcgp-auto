# 账号切换命令行实现计划
# 账号切换命令行实现计划


**目标:** 在 `main_v2.py` 增加 CLI 参数，用于在指定 ADB 设备上切换账号。

**架构:** 扩展参数解析，新增 `--switch-account`，统一设备地址规范化（支持端口简写），然后直接调用 `AccountSwitcher` 注入账号 XML。复用现有仓库查询和 ADB 控制器。

**技术栈:** Python 3.12, SQLModel, argparse, 项目 ADB 基础设施。

### 任务 1: 新增 switch-account 参数解析测试

**文件:**
- 新建: `tests/test_switch_account_cli.py`
- 修改: `src/ptcgp_auto_v2/main.py`

**步骤 1: 编写失败测试**

```python
import unittest


class TestSwitchAccountCLI(unittest.TestCase):
    def test_parse_switch_account_with_port_only_device(self):
        from ptcgp_auto_v2.main import parse_args

        args = parse_args(["--switch-account", "4", "-d", "5715"])
        self.assertEqual(4, args.switch_account)
        self.assertEqual(["5715"], args.devices)
```

**步骤 2: 运行测试并确认失败**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: FAIL，提示 `--switch-account` 未定义或 `parse_args` 不支持传入参数。

**步骤 3: 最小实现**

```python
def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--switch-account", type=int, help="切换到指定账号")
    return parser.parse_args(argv)
```

**步骤 4: 运行测试并确认通过**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: PASS

**步骤 5: 提交**

```bash
git add tests/test_switch_account_cli.py src/ptcgp_auto_v2/main.py
git commit -m "test(cli): add switch-account arg parsing" -m "补充 switch-account 参数解析测试。"
```

### 任务 2: 设备地址规范化

**文件:**
- 修改: `src/ptcgp_auto_v2/main.py`

**步骤 1: 编写失败测试**

```python
def test_normalize_device_addresses_port_only(self):
    from ptcgp_auto_v2.main import normalize_device_addresses

    self.assertEqual(["127.0.0.1:5715"], normalize_device_addresses(["5715"]))
```

**步骤 2: 运行测试并确认失败**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: FAIL，提示 helper 不存在。

**步骤 3: 最小实现**

```python
def normalize_device_addresses(devices: list[str]) -> list[str]:
    normalized = []
    for device in devices:
        if device.isdigit():
            normalized.append(f"127.0.0.1:{device}")
        elif ":" in device:
            normalized.append(device)
        else:
            raise ValueError(f"invalid device address: {device}")
    return normalized
```

**步骤 4: 运行测试并确认通过**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: PASS

**步骤 5: 提交**

```bash
git add tests/test_switch_account_cli.py src/ptcgp_auto_v2/main.py
git commit -m "feat(cli): add switch-account device normalization" -m "支持端口简写设备地址并提供校验。"
```

### 任务 3: 接入切换账号流程

**文件:**
- 修改: `src/ptcgp_auto_v2/main.py`

**步骤 1: 编写失败测试**

```python
from unittest.mock import patch


def test_switch_account_command_executes(self):
    from ptcgp_auto_v2 import main as main_module

    with patch.object(main_module, "AccountRepository") as repo_cls, \
         patch.object(main_module, "AdbController") as adb_cls, \
         patch.object(main_module, "AccountSwitcher") as switcher_cls, \
         patch.object(main_module, "get_database"):
        repo = repo_cls.return_value
        account = type("Account", (), {"id": 4, "game_id": "gid", "nickname": "nick", "xml_content": b"x"})
        repo.get_by_id.return_value = account
        adb = adb_cls.return_value
        switcher = switcher_cls.return_value
        switcher.switch_to.return_value = True

        exit_code = main_module.run_switch_account("127.0.0.1:5715", 4)

        adb.connect.assert_called_once()
        switcher.switch_to.assert_called_once()
        self.assertEqual(0, exit_code)
```

**步骤 2: 运行测试并确认失败**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: FAIL，提示 `run_switch_account` 不存在。

**步骤 3: 最小实现**

```python
def run_switch_account(device: str, account_id: int) -> int:
    repo = AccountRepository()
    account = repo.get_by_id(account_id)
    if not account or not account.xml_content:
        return 1

    adb = AdbController(device)
    adb.connect()
    try:
        switcher = AccountSwitcher(adb)
        return 0 if switcher.switch_to(account, restart_app=True) else 1
    finally:
        adb.disconnect()
```

**步骤 4: 运行测试并确认通过**

运行: `python -m unittest tests/test_switch_account_cli.py`

预期: PASS

**步骤 5: 提交**

```bash
git add tests/test_switch_account_cli.py src/ptcgp_auto_v2/main.py
git commit -m "feat(cli): add switch-account execution" -m "在主入口添加账号切换命令。"
```
