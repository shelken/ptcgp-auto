#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTCGP 调试工具

入口文件 - 转发到 v2 版本
"""

import sys
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

# 导入并运行 v2 版本
from ptcgp_auto_v2.tools.debug_tool import main

if __name__ == "__main__":
    main()
