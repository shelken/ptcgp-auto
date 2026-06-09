# -*- coding: utf-8 -*-
"""manage_friendship 好友图标只读实机探针场景元信息。

这个场景只验证真实设备截图与模板匹配链路，不执行好友申请、删除、取消邀请、确认等社交动作。未覆盖真实申请/删除/取消邀请闭环。
"""

from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "device": E2EScenarioConfig(
        case_id="friend_icon_readonly_probe",
        profile="device",
        description=(
            "只读验证 manage_friendship 好友绿勾/红叉模板在真实截图上的 "
            "1.0 与 0.8 scale 检测链路；不覆盖真实申请/删除/取消邀请闭环"
        ),
        task_type="manage_friendship",
        allow_skipped=False,
        params={
            "adb_timeout_seconds": 8,
            "probe_timeout_seconds": 25,
        },
    ),
}
