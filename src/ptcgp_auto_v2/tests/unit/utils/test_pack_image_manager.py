# -*- coding: utf-8 -*-

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.urls.append(url)
        return self.response

    def close(self) -> None:
        pass


def pack_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (160, 256), (220, 120, 80)).save(buffer, "WEBP")
    return buffer.getvalue()


def test_ensure_pack_ready_downloads_ptcgp_assets_url_and_saves_to_assets_dir(tmp_path):
    image_url = "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images/en-US/packs/B1_3.webp"
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession(FakeResponse(pack_image_bytes()))
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda booster_name: SimpleNamespace(  # type: ignore[method-assign]
        name=booster_name,
        set_code="B1",
        label_data='{"en":"Mega Altaria"}',
        sku_id="B1_3",
        image_url=image_url,
    )

    assert manager.ensure_pack_ready("Mega Altaria") is True

    assert fake_session.urls == [image_url]
    assert "flibustier" not in fake_session.urls[0]
    assert manager.get_pack_path("Mega Altaria") == tmp_path / "templates" / "packs_auto_assets" / "Mega_Altaria.png"
    assert manager.get_pack_path("Mega Altaria").exists()
    assert manager.get_template_name("Mega Altaria") == "packs_auto_assets/Mega_Altaria"


def test_ensure_pack_ready_returns_false_when_pack_image_url_missing(tmp_path):
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession(FakeResponse(pack_image_bytes()))
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda booster_name: SimpleNamespace(  # type: ignore[method-assign]
        name=booster_name,
        set_code="B1",
        label_data='{"en":"Mega Altaria"}',
        sku_id="B1_3",
        image_url=None,
    )

    assert manager.ensure_pack_ready("Mega Altaria") is False

    assert fake_session.urls == []
    assert not manager.get_pack_path("Mega Altaria").exists()
