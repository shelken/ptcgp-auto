# -*- coding: utf-8 -*-
"""core 场景模板。"""


def run(ctx):
    """实现 core 版本流程。"""
    ctx.log(ctx.config.description)
    raise NotImplementedError("copy this template and implement core run(ctx)")

