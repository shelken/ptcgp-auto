import json


def build_label_dict(raw: str | None) -> dict:
    """解析 label_data 为字典。"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
