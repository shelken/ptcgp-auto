# -*- coding: utf-8 -*-
"""scheduler_idle_backoff 场景元信息。

这个文件负责声明空转退避场景配置。
覆盖有 pending 任务但本轮无法真正提交执行器的观察窗口。
关键依赖是 E2E 场景加载约定和 claim_gifts 任务注册结果。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="scheduler_idle_backoff",
        profile="core",
        description="验证调度器在无法派发 pending 任务时会按轮询间隔退避",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "poll_interval_seconds": 0.2,
            "observe_cycles": 4,
        },
    ),
}
