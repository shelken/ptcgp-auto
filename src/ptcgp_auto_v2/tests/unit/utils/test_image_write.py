# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import pytest

from ptcgp_auto_v2.utils.image_write import write_bytes_atomic


def test_write_bytes_atomic_replaces_existing_file(tmp_path):
    target = tmp_path / "card.png"
    target.write_bytes(b"old-image")

    write_bytes_atomic(target, b"new-image")

    assert target.read_bytes() == b"new-image"
    assert list(tmp_path.glob(".card.png.*.tmp")) == []


def test_write_bytes_atomic_keeps_existing_file_when_temp_write_fails(tmp_path, monkeypatch):
    target = tmp_path / "card.png"
    target.write_bytes(b"old-image")
    original_write_bytes = Path.write_bytes

    def fail_temp_write(path: Path, content: bytes) -> int:
        if path.name.startswith(".card.png.") and path.name.endswith(".tmp"):
            raise OSError("磁盘写入失败")
        return original_write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail_temp_write)

    with pytest.raises(OSError, match="磁盘写入失败"):
        write_bytes_atomic(target, b"new-image")

    assert target.read_bytes() == b"old-image"
    assert list(tmp_path.glob(".card.png.*.tmp")) == []
