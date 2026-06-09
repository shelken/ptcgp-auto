# -*- coding: utf-8 -*-
"""card_scan_readonly_probe 场景元信息。

只读验证 send_card_daily/exchange_cards 共用选卡扫描 helper 的实机前置链路。
未覆盖最终送卡/交换确认，也不点击送出、交换、确认按钮。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "device": E2EScenarioConfig(
        case_id="card_scan_readonly_probe",
        profile="device",
        description=(
            "只读探测送卡/交换选卡扫描：ADB/u2/启动 app/page detect 后，"
            "调用共享扫描签名与稳定轮数 helper；未覆盖最终送卡/交换确认"
        ),
        task_type="send_card_daily",
        allow_skipped=False,
        params={
            "command_timeout_seconds": 10,
            "page_detect_timeout_seconds": 30,
            "scan_probe_timeout_seconds": 10,
        },
    ),
}
