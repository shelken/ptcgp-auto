# -*- coding: utf-8 -*-
"""device_probe_chain 场景元信息。

这个文件声明短设备探针场景，用于把完整实机 E2E 卡点拆到 ADB、uiautomator2、截图、prepare 与页面识别边界。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "device": E2EScenarioConfig(
        case_id="device_probe_chain",
        profile="device",
        description="短链路定位实机 E2E 卡点：ADB/u2/截图/prepare/page detect",
        task_type="claim_rewards",
        allow_skipped=False,
        params={
            "command_timeout_seconds": 10,
            "prepare_timeout_seconds": 30,
            "page_detect_timeout_seconds": 30,
        },
    ),
}
