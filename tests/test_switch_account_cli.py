import sys
import unittest
from unittest import mock
from pathlib import Path

# 添加 src 目录到 Python 路径
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.main import (
    normalize_device_addresses,
    parse_args,
    run_switch_account,
)


class TestSwitchAccountCli(unittest.TestCase):
    def test_parse_switch_account_with_port_only_device(self):
        args = parse_args(["--switch-account", "4", "-d", "5715"])

        self.assertEqual(args.switch_account, 4)
        self.assertEqual(args.devices, ["5715"])

    def test_normalize_device_addresses_port_only(self):
        self.assertEqual(normalize_device_addresses(["5715"]), ["127.0.0.1:5715"])

    def test_normalize_device_addresses_invalid(self):
        with self.assertRaises(ValueError):
            normalize_device_addresses(["bad-address"])

    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.AccountSwitcher")
    @mock.patch("ptcgp_auto_v2.main.AdbController")
    @mock.patch("ptcgp_auto_v2.main.AccountRepository")
    def test_switch_account_command_executes(
        self,
        mock_repo_cls,
        mock_adb_cls,
        mock_switcher_cls,
        mock_get_database,
    ):
        account = mock.Mock()
        account.xml_content = b"<xml>content</xml>"
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_id.return_value = account

        mock_adb = mock_adb_cls.return_value
        mock_switcher = mock_switcher_cls.return_value
        mock_switcher.switch_to.return_value = True

        result = run_switch_account("127.0.0.1:5715", 4)

        mock_get_database.assert_called_once_with()
        mock_adb.connect.assert_called_once_with()
        mock_switcher.switch_to.assert_called_once_with(account, restart_app=True)
        self.assertEqual(result, 0)

    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.AdbController")
    @mock.patch("ptcgp_auto_v2.main.AccountRepository")
    def test_switch_account_missing_xml_returns_error(
        self,
        mock_repo_cls,
        mock_adb_cls,
        mock_get_database,
    ):
        account = mock.Mock()
        account.xml_content = None
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_id.return_value = account

        result = run_switch_account("127.0.0.1:5715", 4)

        mock_get_database.assert_called_once_with()
        mock_adb_cls.assert_not_called()
        self.assertEqual(result, 1)

    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.AccountSwitcher")
    @mock.patch("ptcgp_auto_v2.main.AdbController")
    @mock.patch("ptcgp_auto_v2.main.AccountRepository")
    def test_switch_account_switch_failure_returns_error(
        self,
        mock_repo_cls,
        mock_adb_cls,
        mock_switcher_cls,
        mock_get_database,
    ):
        account = mock.Mock()
        account.xml_content = b"<xml>content</xml>"
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_id.return_value = account

        mock_switcher = mock_switcher_cls.return_value
        mock_switcher.switch_to.return_value = False

        result = run_switch_account("127.0.0.1:5715", 4)

        mock_get_database.assert_called_once_with()
        mock_adb_cls.return_value.connect.assert_called_once_with()
        mock_switcher.switch_to.assert_called_once_with(account, restart_app=True)
        self.assertEqual(result, 1)

    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.AccountSwitcher")
    @mock.patch("ptcgp_auto_v2.main.AdbController")
    @mock.patch("ptcgp_auto_v2.main.AccountRepository")
    def test_switch_account_exception_returns_error(
        self,
        mock_repo_cls,
        mock_adb_cls,
        mock_switcher_cls,
        mock_get_database,
    ):
        account = mock.Mock()
        account.xml_content = b"<xml>content</xml>"
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_by_id.return_value = account

        mock_switcher = mock_switcher_cls.return_value
        mock_switcher.switch_to.side_effect = RuntimeError("boom")

        result = run_switch_account("127.0.0.1:5715", 4)

        mock_get_database.assert_called_once_with()
        mock_adb_cls.return_value.connect.assert_called_once_with()
        mock_adb_cls.return_value.disconnect.assert_called_once_with()
        self.assertEqual(result, 1)

    @mock.patch("ptcgp_auto_v2.main.run_switch_account")
    @mock.patch("ptcgp_auto_v2.main.set_settings")
    @mock.patch("ptcgp_auto_v2.main.Settings")
    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.discover_devices")
    @mock.patch("ptcgp_auto_v2.main.parse_args")
    def test_main_switch_account_conflict_with_task_returns_error(
        self,
        mock_parse_args,
        mock_discover_devices,
        mock_get_database,
        mock_settings_cls,
        mock_set_settings,
        mock_run_switch_account,
    ):
        mock_parse_args.return_value = mock.Mock(
            devices=["5715"],
            daemon=False,
            single=False,
            task=["open_pack"],
            account=None,
            list_tasks=False,
            list_accounts=False,
            sync_account=False,
            reset_running=False,
            workers=1,
            debug=False,
            disable_switch=False,
            switch_account=1,
        )
        mock_discover_devices.return_value = ["127.0.0.1:5555"]
        mock_settings = mock_settings_cls.return_value
        mock_settings.configure_logging.return_value = None

        from ptcgp_auto_v2 import main as main_module

        result = main_module.main()

        mock_get_database.assert_called_once_with()
        mock_run_switch_account.assert_not_called()
        self.assertEqual(result, 1)

    @mock.patch("ptcgp_auto_v2.main.run_switch_account")
    @mock.patch("ptcgp_auto_v2.main.set_settings")
    @mock.patch("ptcgp_auto_v2.main.Settings")
    @mock.patch("ptcgp_auto_v2.main.get_database")
    @mock.patch("ptcgp_auto_v2.main.discover_devices")
    @mock.patch("ptcgp_auto_v2.main.parse_args")
    def test_main_switch_account_conflict_with_daemon_returns_error(
        self,
        mock_parse_args,
        mock_discover_devices,
        mock_get_database,
        mock_settings_cls,
        mock_set_settings,
        mock_run_switch_account,
    ):
        mock_parse_args.return_value = mock.Mock(
            devices=["5715"],
            daemon=True,
            single=False,
            task=None,
            account=None,
            list_tasks=False,
            list_accounts=False,
            sync_account=False,
            reset_running=False,
            workers=1,
            debug=False,
            disable_switch=False,
            switch_account=1,
        )
        mock_discover_devices.return_value = ["127.0.0.1:5555"]
        mock_settings = mock_settings_cls.return_value
        mock_settings.configure_logging.return_value = None

        from ptcgp_auto_v2 import main as main_module

        result = main_module.main()

        mock_get_database.assert_called_once_with()
        mock_run_switch_account.assert_not_called()
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
