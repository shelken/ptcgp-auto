# -*- coding: utf-8 -*-
"""claim_rewards_page_flow 场景元信息。

这个文件负责声明 claim_rewards 实机 E2E 场景。
覆盖真实设备链路里奖励页领取、主题收藏判断与任务完成收敛。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "device": E2EScenarioConfig(
        case_id="claim_rewards_page_flow",
        profile="device",
        description="验证 claim_rewards 在真实设备链路里能完成奖励页和主题收藏流程",
        task_type="claim_rewards",
        allow_skipped=False,
        params={
            "join_timeout_seconds": 360,
            "lease_timeout_seconds": 20,
        },
    ),
}
