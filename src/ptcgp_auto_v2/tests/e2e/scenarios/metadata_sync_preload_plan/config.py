# -*- coding: utf-8 -*-
"""metadata sync 预加载计划 E2E 场景配置。"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="metadata_sync_preload_plan",
        profile="core",
        description=(
            "验证 metadata sync 使用真实服务在隔离 DB 中构建并执行预加载计划，"
            "保持卡牌更新、跳过等价结果与 card_packs 关联语义"
        ),
        task_type="metadata_sync_preload_plan",
        allow_skipped=False,
        params={},
    ),
}
