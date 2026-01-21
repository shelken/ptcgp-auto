"""
工具函数
"""

from pathlib import Path


def get_app_data_dir() -> Path:
    """获取持久化数据目录"""
    data_dir = Path.home() / ".ptcgp_auto"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_data_dir(port: int) -> Path:
    """获取临时数据目录（状态文件、调试截图）"""
    data_dir = Path("/tmp") / f"ptcgp_auto_{port}"
    data_dir.mkdir(exist_ok=True)
    return data_dir
