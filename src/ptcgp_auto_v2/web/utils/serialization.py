# -*- coding: utf-8 -*-
"""Web 服务层序列化工具。"""

from typing import Any


def serialize_account(account: Any) -> dict[str, Any]:
    """把账号模型转成模板可直接消费的纯数据。"""
    data = account.to_dict()
    data["display_name"] = account.display_name
    return data


def serialize_task_plan(plan: Any) -> dict[str, Any]:
    """把任务计划模型转成模板可直接消费的纯数据。"""
    data = plan.to_dict()
    data["task_types_list"] = data["task_types"]
    data["config_dict"] = data["configuration"]
    return data
