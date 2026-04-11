# -*- coding: utf-8 -*-
"""E2E harness 进程采样测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

import ptcgp_auto_v2.tests.e2e.harness as harness_module
from ptcgp_auto_v2.tests.e2e.harness import SchedulerHarness


def test_parse_vmmap_summary_extracts_expected_metrics():
    raw = """
Physical footprint:         114.0M
ReadOnly portion of Libraries: Total=931.4M resident=181.2M(19%) swapped_out_or_unallocated=750.1M(81%)
Writable regions: Total=205.4M written=106.1M(52%) resident=106.2M(52%) swapped_out=0K(0%) unallocated=99.2M(48%)
"""

    metrics = harness_module.parse_vmmap_summary(raw)

    assert metrics == {
        "physical_footprint_mb": 114.0,
        "readonly_libraries_resident_mb": 181.2,
        "writable_regions_resident_mb": 106.2,
    }


def test_extract_loaded_library_matches_filters_patterns():
    raw = """
/tmp/cv2/cv2.abi3.so
/tmp/torch/libtorch.dylib
/tmp/other.dylib
"""

    matched = harness_module.extract_loaded_library_matches(
        raw,
        patterns=["cv2", "torch"],
    )

    assert matched == [
        "/tmp/cv2/cv2.abi3.so",
        "/tmp/torch/libtorch.dylib",
    ]


def test_collect_process_runtime_state_reads_vmmap_and_lsof(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, ...]] = []

    def fake_run(cmd, check, capture_output, text):
        del check, capture_output, text
        calls.append(tuple(cmd))

        class Result:
            def __init__(self, stdout: str):
                self.stdout = stdout

        if cmd[0] == "vmmap":
            return Result(
                "Physical footprint:         114.0M\n"
                "ReadOnly portion of Libraries: Total=931.4M resident=181.2M(19%)\n"
                "Writable regions: Total=205.4M written=106.1M(52%) resident=106.2M(52%)\n"
            )
        if cmd[0] == "lsof":
            return Result("/tmp/cv2/cv2.abi3.so\n/tmp/other.dylib\n")
        raise AssertionError(cmd)

    monkeypatch.setattr(harness_module.subprocess, "run", fake_run)

    harness = SchedulerHarness(
        db_path=Path("/tmp/e2e_process.db"),
        device_addresses=["127.0.0.1:5555"],
    )
    metrics = harness.collect_process_runtime_state(123, patterns=["cv2", "torch"])

    assert metrics["pid"] == 123
    assert metrics["physical_footprint_mb"] == 114.0
    assert metrics["readonly_libraries_resident_mb"] == 181.2
    assert metrics["writable_regions_resident_mb"] == 106.2
    assert metrics["matched_libraries"] == ["/tmp/cv2/cv2.abi3.so"]
    assert calls == [
        ("vmmap", "-summary", "123"),
        ("lsof", "-p", "123"),
    ]
