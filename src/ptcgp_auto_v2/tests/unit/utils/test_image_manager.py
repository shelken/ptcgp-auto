# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time

from ptcgp_auto_v2.utils.image_manager import ImageResourceManager


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code


class CountingSession:
    def __init__(self, content: bytes, delay: float = 0.0) -> None:
        self.content = content
        self.delay = delay
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, url: str, timeout: int) -> FakeResponse:
        with self._lock:
            self.urls.append(url)
        if self.delay:
            time.sleep(self.delay)
        return FakeResponse(self.content)

    def close(self) -> None:
        pass


def test_download_cards_batch_deduplicates_card_numbers(tmp_path):
    manager = ImageResourceManager(base_dir=str(tmp_path / "cards"))
    session = CountingSession(b"image-bytes")
    manager.session = session  # type: ignore[assignment]

    result = manager.download_cards_batch("PROMO-B", [49, 49, 49], max_workers=3)

    assert result == {49: tmp_path / "cards" / "PROMO-B" / "49.png"}
    assert len(session.urls) == 1


def test_download_card_uses_file_lock_across_manager_instances(tmp_path):
    first = ImageResourceManager(base_dir=str(tmp_path / "cards"))
    second = ImageResourceManager(base_dir=str(tmp_path / "cards"))
    first_session = CountingSession(b"image-bytes", delay=0.2)
    second_session = CountingSession(b"image-bytes")
    first.session = first_session  # type: ignore[assignment]
    second.session = second_session  # type: ignore[assignment]

    results = []
    t1 = threading.Thread(target=lambda: results.append(first.download_card("PROMO-B", 49)))
    t2 = threading.Thread(target=lambda: results.append(second.download_card("PROMO-B", 49)))

    t1.start()
    time.sleep(0.05)
    t2.start()
    t1.join()
    t2.join()

    expected_path = tmp_path / "cards" / "PROMO-B" / "49.png"
    assert results == [expected_path, expected_path]
    assert expected_path.read_bytes() == b"image-bytes"
    assert len(first_session.urls) + len(second_session.urls) == 1
    assert not (tmp_path / "cards" / "PROMO-B" / "49.download.lock").exists()
