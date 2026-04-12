# -*- coding: utf-8 -*-
"""scheduler_idle_backoff E2E 场景包。

这个目录负责承载调度器空转退避场景。
覆盖 deterministic core harness 下的待执行任务保留与退避频率。
关键依赖是场景加载器对 config.py 和 core.py 的约定发现。
"""
