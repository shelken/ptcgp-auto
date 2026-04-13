"""
工具函数
"""

from pathlib import Path
def get_data_dir(port: int) -> Path:
    """获取临时数据目录（状态文件、调试截图）"""
    data_dir = Path("/tmp") / f"ptcgp_auto_{port}"
    data_dir.mkdir(exist_ok=True)
    return data_dir
