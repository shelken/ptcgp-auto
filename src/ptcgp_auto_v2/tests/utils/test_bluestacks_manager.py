# -*- coding: utf-8 -*-
"""
BlueStacks 实例管理工具测试
"""

from types import SimpleNamespace

import ptcgp_auto_v2.utils.bluestacks_manager as bluestacks_manager


def test_extract_port_from_address():
    """从 host:port 地址中提取端口。"""
    assert bluestacks_manager.extract_port_from_address("127.0.0.1:5555") == 5555
    assert bluestacks_manager.extract_port_from_address("127.0.0.1") is None
    assert bluestacks_manager.extract_port_from_address("127.0.0.1:abc") is None


def test_parse_instance_from_command():
    """解析 --instance 参数"""
    command = (
        "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks "
        "--instance Tiramisu64_20"
    )
    assert bluestacks_manager.parse_bluestacks_instance(command) == "Tiramisu64_20"


def test_find_instance_by_port(monkeypatch):
    """通过端口推断 PID 与实例名"""

    def fake_run(args, **kwargs):
        if args[:2] == ["lsof", "-n"]:
            return SimpleNamespace(
                stdout=(
                    "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                    "BlueStacks 1234 shelken 123u IPv4 0t0 TCP *:5555 (LISTEN)\n"
                ),
                returncode=0,
            )
        if args[:2] == ["ps", "-p"]:
            return SimpleNamespace(
                stdout=(
                    "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks "
                    "--instance Tiramisu64_20"
                ),
                returncode=0,
            )
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(bluestacks_manager.subprocess, "run", fake_run)

    resolved = bluestacks_manager.find_bluestacks_instance_by_port(5555)
    assert resolved is not None
    pid, instance = resolved
    assert pid == 1234
    assert instance == "Tiramisu64_20"


def test_restart_bluestacks_instance_for_device(monkeypatch):
    """重启当前设备对应的 BlueStacks 实例"""
    calls = []

    monkeypatch.setattr(
        bluestacks_manager,
        "find_bluestacks_instance_by_port",
        lambda port: (1234, "Tiramisu64_20"),
    )
    monkeypatch.setattr(
        bluestacks_manager,
        "wait_for_bluestacks_port",
        lambda *args, **kwargs: True,
    )

    def fake_run(args, **kwargs):
        calls.append(("run", args))
        return SimpleNamespace(stdout="", returncode=0)

    def fake_popen(args, **kwargs):
        calls.append(("popen", args))
        return SimpleNamespace(pid=9999)

    monkeypatch.setattr(bluestacks_manager.subprocess, "run", fake_run)
    monkeypatch.setattr(bluestacks_manager.subprocess, "Popen", fake_popen)

    assert (
        bluestacks_manager.restart_bluestacks_instance_for_device("127.0.0.1:5555")
        is True
    )

    assert ("run", ["kill", "1234"]) in calls
    assert (
        "popen",
        [
            "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks",
            "--instance",
            "Tiramisu64_20",
        ],
    ) in calls


def test_discover_bluestacks_devices(monkeypatch):
    """发现 BlueStacks 设备端口"""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["pgrep", "-f"]:
            return SimpleNamespace(stdout="100\n200\n", returncode=0)
        if args[:2] == ["lsof", "-a"] and "-p" in args:
            pid = args[args.index("-p") + 1]
            if pid == "100":
                return SimpleNamespace(
                    stdout="BlueStacks 100 user 1u IPv4 0t0 TCP *:5555 (LISTEN)\n",
                    returncode=0,
                )
            if pid == "200":
                return SimpleNamespace(
                    stdout="BlueStacks 200 user 1u IPv4 0t0 TCP *:5557 (LISTEN)\n",
                    returncode=0,
                )
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(bluestacks_manager.subprocess, "run", fake_run)

    devices = bluestacks_manager.discover_bluestacks_devices()
    assert devices == ["127.0.0.1:5555", "127.0.0.1:5557"]


def test_list_manageable_instances_from_conf(tmp_path):
    """解析 conf 中的 auto 实例"""
    conf_path = tmp_path / "bluestacks.conf"
    conf_path.write_text(
        "bst.instance.Tiramisu64_20.adb_port=5555\n"
        'bst.instance.Tiramisu64_20.display_name="auto-1"\n'
        "bst.instance.Tiramisu64_22.adb_port=5655\n"
        'bst.instance.Tiramisu64_22.display_name="auto-2"\n'
        "bst.instance.Tiramisu64.adb_port=5755\n"
        'bst.instance.Tiramisu64.display_name="main"\n',
        encoding="utf-8",
    )

    instances = bluestacks_manager.list_manageable_instances(
        str(conf_path), prefix="auto-"
    )
    assert instances == {
        5555: ("Tiramisu64_20", "auto-1"),
        5655: ("Tiramisu64_22", "auto-2"),
    }


def test_start_bluestacks_instance(monkeypatch):
    """启动 BlueStacks 实例"""
    calls = []

    def fake_popen(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(pid=1234)

    monkeypatch.setattr(bluestacks_manager.subprocess, "Popen", fake_popen)

    assert bluestacks_manager.start_bluestacks_instance("auto-1") is True
    assert calls[0][0].endswith("BlueStacks")
    assert calls[0][1:] == ["--instance", "auto-1"]


def test_stop_bluestacks_instance(monkeypatch):
    """关闭 BlueStacks 实例"""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bluestacks_manager.subprocess, "run", fake_run)

    assert bluestacks_manager.stop_bluestacks_instance("auto-1") is True
    assert calls[0][:2] == ["pkill", "-f"]
