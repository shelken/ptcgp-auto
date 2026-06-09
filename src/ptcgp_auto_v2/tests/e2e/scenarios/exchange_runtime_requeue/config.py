# -*- coding: utf-8 -*-
"""交换任务 runtime 延时重排 E2E 场景配置。"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="exchange_runtime_requeue",
        profile="core",
        description="验证 exchange_cards 后置 Hook 只读取 runtime delay 并通过执行器重排任务",
        task_type="exchange_cards",
        allow_skipped=False,
        params={
            "runtime_delay_seconds": 30,
            "runtime_delay_reason": "E2E 等待交换复查",
        },
    ),
}
