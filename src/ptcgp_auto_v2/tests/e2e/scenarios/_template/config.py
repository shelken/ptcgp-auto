# -*- coding: utf-8 -*-
"""复制本文件新增一个 E2E 场景。

这个文件只描述场景元信息。
执行流程按 profile 写在同目录的 `core.py` / `device.py`。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

# 这里要写清楚这个场景在测试什么。
# 如果只做一个 profile，可以只保留对应条目。
CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="replace_me",
        profile="core",
        description="写清楚 core 在验证什么",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "lease_timeout_seconds": 2,
        },
    ),
    "device": E2EScenarioConfig(
        case_id="replace_me",
        profile="device",
        description="写清楚 device 在验证什么",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "lease_timeout_seconds": 8,
        },
    ),
}
