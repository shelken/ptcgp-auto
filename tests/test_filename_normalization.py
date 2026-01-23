
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Import from v2 is safe here in tests
from ptcgp_auto_v2.utils.image_manager import ImageResourceManager
from ptcgp_auto.debug_tools.non_interactive import _prepare_and_load_templates

def test_normalize_name_str():
    """Test the normalization logic in ImageResourceManager"""
    assert ImageResourceManager.normalize_name_str("Celebi ex") == "Celebi_ex"
    assert ImageResourceManager.normalize_name_str("Mewtwo & Mew") == "Mewtwo__Mew"
    assert ImageResourceManager.normalize_name_str("001_Bulbasaur") == "001_Bulbasaur"
    assert ImageResourceManager.normalize_name_str("Card Name!") == "Card_Name" # ! removed

@patch("ptcgp_auto.debug_tools.non_interactive._load_template_from_path")
@patch("ptcgp_auto.debug_tools.non_interactive.Path")
def test_prepare_templates_strict_normalization(mock_path_cls, mock_load):
    """
    Test that _prepare_and_load_templates uses strict normalization
    and does NOT try legacy paths (if we are enforcing strictness).
    """
    mock_recognizer = MagicMock()
    mock_mgr = MagicMock()

    # Setup mock path behavior
    # We want to verify that it constructs path with 'Celebi_ex.png'

    # Mock the chain: Path("templates/cards") / series / pack / filename
    mock_root = MagicMock()
    mock_path_cls.return_value = mock_root

    mock_series = MagicMock()
    mock_root.__truediv__.return_value = mock_series

    mock_pack = MagicMock()
    mock_series.__truediv__.return_value = mock_pack

    mock_file = MagicMock()
    mock_pack.__truediv__.return_value = mock_file

    # Setup existence
    mock_file.exists.return_value = True
    mock_file.stem = "Celebi_ex"

    # Input with spaces
    template_args = ["A1a/Mewtwo/Celebi ex"]

    # Run
    _prepare_and_load_templates(mock_recognizer, template_args, mgr=mock_mgr)

    # Verify calls
    # 1. Ensure pack ready
    mock_mgr.ensure_pack_ready.assert_called_with("Mewtwo", "A1a")

    # 2. Verify Path construction arguments
    # Expect: root / "A1a" / "Mewtwo" / "Celebi_ex.png"
    # We can check the calls to __truediv__

    # mock_root / "A1a"
    mock_root.__truediv__.assert_called_with("A1a")
    # mock_series / "Mewtwo" (safe_pack)
    mock_series.__truediv__.assert_called_with("Mewtwo")
    # mock_pack / "Celebi_ex.png" (safe_filename)
    mock_pack.__truediv__.assert_called_with("Celebi_ex.png")

    # If the code was using legacy "Celebi ex.png", this assertion would fail
    # (or rather, it would be called with "Celebi ex.png")

    # Also verify we didn't try to check for "Celebi ex.png" (legacy fallback)
    # If we removed fallback, there should be no other calls to mock_pack.__truediv__
    # expecting "Celebi ex.png"

    # Check all calls to mock_pack.__truediv__
    # expected: [call('Celebi_ex.png')]
    assert mock_pack.__truediv__.call_count == 1
    assert mock_pack.__truediv__.call_args == call("Celebi_ex.png")

