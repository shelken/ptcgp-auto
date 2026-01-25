import pytest
from unittest.mock import MagicMock, patch
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer, DeviceAccountInfo
from ptcgp_auto_v2.db.models import Account

# --- AdbController Tests ---

@pytest.fixture
def mock_adb_device():
    with patch('ptcgp_auto_v2.infra.adb.adb') as mock_adb:
        mock_device = MagicMock()
        mock_adb.device.return_value = mock_device
        yield mock_device

@pytest.fixture
def adb_controller(mock_adb_device):
    controller = AdbController("127.0.0.1:5555")
    controller.connect()
    return controller

def test_adb_is_rooted_true(adb_controller, mock_adb_device):
    # Mock su -c 'id' returning uid=0
    mock_adb_device.shell.return_value = "uid=0(root) gid=0(root)"

    assert adb_controller.is_rooted() is True
    # Verify caching: call again, should not call shell
    mock_adb_device.shell.reset_mock()
    assert adb_controller.is_rooted() is True
    mock_adb_device.shell.assert_not_called()

def test_adb_is_rooted_false(adb_controller, mock_adb_device):
    # Mock su -c 'id' returning non-root or error
    mock_adb_device.shell.return_value = "uid=2000(shell) gid=2000(shell)"

    assert adb_controller.is_rooted() is False

def test_adb_run_as_root(adb_controller, mock_adb_device):
    adb_controller._is_rooted = True

    # Test normal command
    adb_controller.run_as_root("ls /data")
    mock_adb_device.shell.assert_called_with("su -c 'ls /data'")

    # Test command with single quotes (escaping)
    adb_controller.run_as_root("echo 'hello'")
    mock_adb_device.shell.assert_called_with(r"su -c 'echo '\''hello'\'''")

def test_adb_run_as_root_not_rooted(adb_controller):
    adb_controller._is_rooted = False
    result = adb_controller.run_as_root("ls")
    assert result is None

# --- AccountSwitcher Tests ---

@pytest.fixture
def mock_adb_controller():
    controller = MagicMock(spec=AdbController)
    controller.is_rooted.return_value = True
    return controller

def test_switcher_uses_adb_methods(mock_adb_controller):
    switcher = AccountSwitcher(mock_adb_controller)
    account = Account(game_id="test_id", xml_content=b"<xml>test</xml>")

    # Mock internal methods to isolate switch_to logic
    switcher._write_temp_xml = MagicMock(return_value="/tmp/test.xml")
    switcher.inject_xml = MagicMock(return_value=True)

    # Call switch_to to verify it triggers internal logic checks
    switcher.switch_to(account)

    # We verify that switch_to eventually would check for root via adb
    # NOTE: Since we mocked inject_xml which contains the root check, we can't easily verify
    # is_rooted was called unless we mock inject_xml NOT to be replaced, or test inject_xml directly.
    # Let's verify inject_xml logic separately.

    # But since we removed is_rooted from AccountSwitcher API, we confirm it's gone
    assert not hasattr(switcher, 'is_rooted')

def test_switcher_inject_xml_calls_adb_is_rooted(mock_adb_controller):
    switcher = AccountSwitcher(mock_adb_controller)
    switcher._settings = MagicMock()
    switcher._settings.files_to_clean_on_switch = []

    with patch('ptcgp_auto_v2.infra.account_switcher.Path') as MockPath:
        mock_path_obj = MockPath.return_value
        mock_path_obj.exists.return_value = True

        switcher.inject_xml("dummy_path")

        # Verify calls to adb.is_rooted
        mock_adb_controller.is_rooted.assert_called()

def test_switcher_inject_xml_calls_adb_run_as_root(mock_adb_controller):
    switcher = AccountSwitcher(mock_adb_controller)

    # Mock settings
    switcher._settings = MagicMock()
    switcher._settings.files_to_clean_on_switch = []

    with patch('ptcgp_auto_v2.infra.account_switcher.Path') as MockPath:
        mock_path_obj = MockPath.return_value
        mock_path_obj.exists.return_value = True

        switcher.inject_xml("dummy_path", restart_app=False)

        # Verify calls to adb.run_as_root
        assert mock_adb_controller.run_as_root.call_count >= 1
        # Check for specific command like mkdir
        mkdir_calls = [args for args, _ in mock_adb_controller.run_as_root.call_args_list if "mkdir" in args[0]]
        assert len(mkdir_calls) > 0

def test_switcher_clean_device_xml(mock_adb_controller):
    switcher = AccountSwitcher(mock_adb_controller)

    # Test successful cleanup
    result = switcher.clean_device_xml()
    assert result is True
    mock_adb_controller.run_as_root.assert_called()
    assert "rm" in mock_adb_controller.run_as_root.call_args[0][0]

    # Test exception handling
    mock_adb_controller.run_as_root.side_effect = Exception("error")
    result = switcher.clean_device_xml()
    assert result is False

def test_switcher_reset_game_environment(mock_adb_controller):
    switcher = AccountSwitcher(mock_adb_controller)
    # Mock settings
    switcher._settings = MagicMock()
    switcher._settings.app_package = "com.test.app"
    switcher._settings.files_to_clean_on_switch = ["file1", "file2"]

    # Mock internal clean methods
    switcher.clean_device_xml = MagicMock()

    switcher.reset_game_environment()

    # Verify steps
    mock_adb_controller.force_stop.assert_called_with("com.test.app")
    switcher.clean_device_xml.assert_called()
    mock_adb_controller.run_as_root.assert_any_call("rm -f file1")

# --- AccountSyncer Tests ---

@pytest.fixture
def account_syncer(mock_adb_controller):
    return AccountSyncer(mock_adb_controller, storage_dir=MagicMock())

def test_update_account_from_info(account_syncer):
    account = Account(
        game_id="game_123",
        nintendo_id="old_nin",
        country="JP",
        session_token_iat=1000,
        xml_content=b"old"
    )

    new_info = DeviceAccountInfo(
        device_account="game_123",
        nintendo_id="new_nin", # Changed
        country="JP",          # Same
        session_token_iat=2000, # Newer
        xml_content=b"new"
    )

    updated = account_syncer._update_account_from_info(account, new_info)

    assert updated is True
    assert account.nintendo_id == "new_nin"
    assert account.session_token_iat == 2000
    assert account.xml_content == b"new"

def test_update_account_no_changes(account_syncer):
    account = Account(
        game_id="game_123",
        nintendo_id="nin",
        country="JP",
        session_token_iat=1000,
        xml_content=b"xml"
    )

    info = DeviceAccountInfo(
        device_account="game_123",
        nintendo_id="nin",
        country="JP",
        session_token_iat=1000,
        xml_content=b"xml"
    )

    updated = account_syncer._update_account_from_info(account, info)
    assert updated is False

