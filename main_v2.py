#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTCGP Auto v2 入口脚本

使用方式:
    python main_v2.py --daemon                    # 守护模式
    python main_v2.py --list-tasks                # 列出任务
    python main_v2.py --list-accounts             # 列出账号
    python main_v2.py --task open_pack --account 1  # 单任务
"""

import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.main import main

if __name__ == "__main__":
    sys.exit(main())
