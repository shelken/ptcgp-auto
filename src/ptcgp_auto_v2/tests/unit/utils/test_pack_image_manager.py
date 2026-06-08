# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

from ptcgp_auto_v2.config.assets import build_pack_image_url
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import SETS_URL
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.urls.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        pass


def pack_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (160, 256), (220, 120, 80)).save(buffer, "WEBP")
    return buffer.getvalue()


def sets_response(packs: list[Any]) -> FakeResponse:
    return FakeResponse(json.dumps({"sets": [{"code": "B1", "packs": packs}]}).encode("utf-8"))


def test_ensure_pack_ready_downloads_db_image_url_and_saves_to_assets_dir(tmp_path):
    image_url = "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images/en-US/packs/B1_3.webp"
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession({image_url: FakeResponse(pack_image_bytes())})
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
    assert all("flibustier" not in url for url in fake_session.urls)
    assert manager.get_pack_path("Mega Altaria") == tmp_path / "templates" / "packs_auto_assets" / "Mega_Altaria.png"
    assert manager.get_pack_path("Mega Altaria").exists()
    assert manager.get_template_name("Mega Altaria") == "packs_auto_assets/Mega_Altaria"


def test_ensure_pack_ready_resolves_remote_sets_when_db_image_url_missing(tmp_path):
    image_url = build_pack_image_url("B1_3")
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession(
        {
            SETS_URL: sets_response([{"name": "Mega Altaria", "skuId": "B1_3"}]),
            image_url: FakeResponse(pack_image_bytes()),
        }
    )
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda booster_name: SimpleNamespace(  # type: ignore[method-assign]
        name=booster_name,
        set_code="B1",
        label_data='{"en":"Mega Altaria"}',
        sku_id="B1_3",
        image_url=None,
    )

    assert manager.ensure_pack_ready("Mega Altaria") is True

    assert fake_session.urls == [SETS_URL, image_url]
    assert all("flibustier" not in url for url in fake_session.urls)
    assert manager.get_pack_path("Mega Altaria").exists()


def test_ensure_pack_ready_resolves_remote_sets_when_db_pack_missing(tmp_path):
    image_url = build_pack_image_url("B1_4")
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession(
        {
            SETS_URL: sets_response(["Legacy Entry", {"name": "Mega Gyarados", "skuId": "B1_4"}]),
            image_url: FakeResponse(pack_image_bytes()),
        }
    )
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda _booster_name: None  # type: ignore[method-assign]

    assert manager.ensure_pack_ready("Mega Gyarados") is True

    assert fake_session.urls == [SETS_URL, image_url]
    assert all("flibustier" not in url for url in fake_session.urls)
    assert manager.get_pack_path("Mega Gyarados").exists()


def test_ensure_pack_ready_returns_false_when_remote_sets_missing_booster_name(tmp_path):
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession({SETS_URL: sets_response([{"name": "Mega Gyarados", "skuId": "B1_4"}])})
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda _booster_name: None  # type: ignore[method-assign]

    assert manager.ensure_pack_ready("Mega Altaria") is False

    assert fake_session.urls == [SETS_URL]
    assert all("flibustier" not in url for url in fake_session.urls)
    assert not manager.get_pack_path("Mega Altaria").exists()


def test_ensure_pack_ready_returns_false_when_remote_sets_request_fails(tmp_path):
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    fake_session = FakeSession({SETS_URL: RuntimeError("network down")})
    manager.session = fake_session  # type: ignore[assignment]
    manager.get_pack_metadata = lambda _booster_name: None  # type: ignore[method-assign]

    assert manager.ensure_pack_ready("Mega Altaria") is False

    assert fake_session.urls == [SETS_URL]
    assert not manager.get_pack_path("Mega Altaria").exists()


def test_process_and_save_keeps_existing_pack_image_when_save_fails(tmp_path, monkeypatch):
    manager = PackImageManager(base_dir=str(tmp_path / "templates" / "packs_auto_assets"))
    save_path = manager.get_pack_path("Mega Altaria")
    save_path.write_bytes(b"old-pack-image")
    image_data = pack_image_bytes()

    def fail_after_partial_write(self, fp, *args, **kwargs):
        if isinstance(fp, str | Path):
            Path(fp).write_bytes(b"partial-pack-image")
        raise OSError("PNG 保存失败")

    monkeypatch.setattr(Image.Image, "save", fail_after_partial_write)

    assert manager.process_and_save("Mega Altaria", image_data) is False
    assert save_path.read_bytes() == b"old-pack-image"
    assert list(save_path.parent.glob(".Mega_Altaria.png.*.tmp")) == []
