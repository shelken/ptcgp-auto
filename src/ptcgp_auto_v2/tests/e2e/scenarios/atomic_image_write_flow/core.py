# -*- coding: utf-8 -*-
"""原子图片写入 core E2E 场景。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from ptcgp_auto_v2.utils.image_manager import ImageResourceManager
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: int) -> _FakeResponse:
        del timeout
        self.urls.append(url)
        filename = url.rsplit("/", 1)[-1]
        return self.responses[filename]

    def close(self) -> None:
        pass


def _image_bytes(image_format: str, size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, image_format)
    return buffer.getvalue()


def _assert_image_size(path: Path, expected_size: tuple[int, int]) -> None:
    with Image.open(path) as image:
        image.load()
        assert image.size == expected_size


def _assert_no_atomic_temps(directory: Path) -> None:
    assert list(directory.glob(".*.tmp")) == []


def run(ctx):
    """执行卡图/包图原子写入轻量链路。"""
    ctx.log(ctx.config.description)
    root = ctx.harness.db_path.parent / "atomic_image_write_flow"
    cards_dir = root / "cards"
    packs_dir = root / "packs"

    card_png = _image_bytes("PNG", (12, 8), (40, 120, 220))
    pack_webp = _image_bytes("WEBP", (160, 256), (220, 120, 80))

    card_manager = ImageResourceManager(base_dir=str(cards_dir))
    card_manager.session = _FakeSession(  # type: ignore[assignment]
        {
            "7.png": _FakeResponse(card_png),
            "99.png": _FakeResponse(_image_bytes("PNG", (12, 8), (200, 50, 40))),
        }
    )
    pack_manager = PackImageManager(base_dir=str(packs_dir))

    card_path = card_manager.download_card("E2E", 7)
    assert card_path == cards_dir / "E2E" / "7.png"
    _assert_image_size(card_path, (12, 8))
    _assert_no_atomic_temps(card_path.parent)

    assert pack_manager.process_and_save("Atomic Pack", pack_webp) is True
    pack_path = pack_manager.get_pack_path("Atomic Pack")
    assert pack_path == packs_dir / "Atomic_Pack.png"
    _assert_image_size(pack_path, (103, 54))
    _assert_no_atomic_temps(pack_path.parent)

    old_card = _image_bytes("PNG", (5, 4), (10, 20, 30))
    old_pack = _image_bytes("PNG", (6, 5), (30, 20, 10))
    failing_card_path = cards_dir / "E2E_FAIL" / "99.png"
    failing_card_path.parent.mkdir(parents=True, exist_ok=True)
    failing_card_path.write_bytes(old_card)
    failing_pack_path = pack_manager.get_pack_path("Failing Pack")
    failing_pack_path.write_bytes(old_pack)

    original_write_bytes = Path.write_bytes

    def fail_atomic_temp_write(path: Path, content: bytes) -> int:
        if path.name.endswith(".tmp"):
            raise OSError("E2E 模拟 atomic 临时文件写入失败")
        return original_write_bytes(path, content)

    ctx.monkeypatch.setattr(Path, "write_bytes", fail_atomic_temp_write)

    # 变更原因：download_card 发现旧文件会直接返回；这里用锁内真实保存路径验证覆盖失败不会破坏旧卡图。
    assert card_manager._download_card_locked("E2E_FAIL", 99, failing_card_path.parent) is None
    _assert_image_size(failing_card_path, (5, 4))
    assert failing_card_path.read_bytes() == old_card
    _assert_no_atomic_temps(failing_card_path.parent)

    assert pack_manager.process_and_save("Failing Pack", pack_webp) is False
    _assert_image_size(failing_pack_path, (6, 5))
    assert failing_pack_path.read_bytes() == old_pack
    _assert_no_atomic_temps(failing_pack_path.parent)

    assert card_path.read_bytes() != pack_path.read_bytes()
    card_manager.close()
    pack_manager.close()
