from datetime import datetime


def format_datetime(value: datetime | None) -> str:
    """格式化时间为可读字符串。"""
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_datetime_iso(value: datetime | None) -> str | None:
    """格式化时间为 ISO 8601 字符串。"""
    if not value:
        return None
    return value.isoformat(timespec="seconds")
