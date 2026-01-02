"""
工具函数
"""

import tempfile
from pathlib import Path


def get_data_dir(port: int) -> Path:
    """获取指定端口的数据目录（临时目录）"""
    data_dir = Path(tempfile.gettempdir()) / f"ptcgp_auto_{port}"
    data_dir.mkdir(exist_ok=True)
    return data_dir
