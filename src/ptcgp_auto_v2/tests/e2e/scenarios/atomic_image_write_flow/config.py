# -*- coding: utf-8 -*-
"""原子图片写入 core E2E 场景配置。"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="atomic_image_write_flow",
        profile="core",
        description="验证卡图/包图保存共用原子写入行为，失败保留旧文件并清理临时文件",
        task_type="claim_gifts",
        allow_skipped=False,
        params={},
    ),
}
