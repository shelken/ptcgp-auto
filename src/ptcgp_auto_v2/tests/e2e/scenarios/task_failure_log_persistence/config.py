# -*- coding: utf-8 -*-
"""失败任务日志持久化 E2E 场景配置。"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="task_failure_log_persistence",
        profile="core",
        description="验证失败任务会把当次 TRACE 日志结构化写入 data/logs",
        task_type="e2e_failure_log_task",
        allow_skipped=False,
        params={
            "failure_reason": "e2e 故意失败",
        },
    ),
}
