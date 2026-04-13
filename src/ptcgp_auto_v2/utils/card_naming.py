# -*- coding: utf-8 -*-
"""
卡牌命名工具
用于处理卡牌文件名标准化、解析等逻辑，避免 Repository 和 ImageManager 之间的循环依赖。
"""

def normalize_name_str(name: str) -> str:
    """统一的文件名标准化逻辑：过滤特殊字符 + 空格转下划线"""
    # 保留字母数字、横杠、下划线、空格
    safe_name = "".join([c for c in name if c.isalnum() or c in " -_"])
    # 将空格替换为下划线
    return safe_name.replace(" ", "_")
