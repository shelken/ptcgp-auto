# -*- coding: utf-8 -*-
"""定义 fetch_account_info 实机 E2E 场景元信息。

这个文件负责声明 fetch_account_info 场景的 device 运行配置。这个场景覆盖真实设备上的账号资料与资源回写完成路径。它依赖 E2E 场景加载约定和 `fetch_account_info` 任务注册结果。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "device": E2EScenarioConfig(
        case_id="fetch_account_info_completion",
        profile="device",
        description="验证 fetch_account_info 在真实设备链路里会回写账号资料与资源",
        task_type="fetch_account_info",
        allow_skipped=False,
        params={
            "join_timeout_seconds": 300,
            "lease_timeout_seconds": 12,
        },
    ),
}
