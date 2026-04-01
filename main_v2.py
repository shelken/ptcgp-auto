#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTCGP Auto v2 入口脚本

使用方式:
    uv run python main_v2.py --daemon                    # 守护模式
    uv run python main_v2.py --list-tasks                # 列出任务
    uv run python main_v2.py --list-accounts             # 列出账号
    uv run python main_v2.py --task open_pack --account 1  # 单任务
"""

import sys

from ptcgp_auto_v2.main import main

if __name__ == "__main__":
    sys.exit(main())
