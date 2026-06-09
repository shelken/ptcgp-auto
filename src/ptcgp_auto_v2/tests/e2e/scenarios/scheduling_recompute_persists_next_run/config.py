# -*- coding: utf-8 -*-
"""调度重算落库 E2E 场景配置。"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="scheduling_recompute_persists_next_run",
        profile="core",
        description="验证真实调度重算路径会持久化 next_run_at/reset_type/updated_at",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "interval_seconds": 3600,
        },
    ),
}
