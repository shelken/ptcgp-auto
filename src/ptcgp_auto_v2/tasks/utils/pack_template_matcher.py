# -*- coding: utf-8 -*-
"""卡包模板匹配器（packs_auto）

这是一个纯工具类：
- 输入：候选子包列表（调用方准备 pack 表数据后传入）
- 输出：最高置信度命中的子包（低于阈值返回 None）

约束：
- 不负责读取 pack 表/仓库；候选数据必须由调用方传入。
- 不负责页面点击/滑动等动作。
- 会话内记录本次加载的模板名，供调用方在任务结束时卸载。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PackCandidate:
    """候选子包信息。

    set_code：系列代码。
    booster_name：子包名称，对应 packs_auto/<name>.png 模板。
    """

    set_code: str
    booster_name: str


@dataclass(frozen=True)
class PackTemplateMatch:
    """模板匹配结果。"""

    candidate: PackCandidate
    confidence: float
    box: tuple[int, int, int, int]


class PackTemplateMatcher:
    """packs_auto 模板匹配器。

    语义：在候选子包中，计算每个模板的最高置信度，返回最高者；
    若最高置信度 < threshold，则返回 None。
    """

    # TemplateMatcher.find_with_scale 内部用了 `threshold or self.threshold`，不能传 0.0
    _SCORE_THRESHOLD_EPS = 1e-6

    def __init__(self, template_matcher: Any, pack_image_manager: Any):
        self._template_matcher = template_matcher
        self._pack_image_manager = pack_image_manager
        self._session_loaded_templates: set[str] = set()

    def prepare(self, candidates: list[PackCandidate]) -> dict[str, bool]:
        """准备候选模板（下载图片 + 加载模板）。

        Returns:
            dict[booster_name, ok]
        """
        ready: dict[str, bool] = {}
        for c in candidates:
            name = c.booster_name
            if not name:
                continue
            ready[name] = self._ensure_template_loaded(name)
        return ready

    def match_best(
        self,
        screenshot: Any,
        candidates: list[PackCandidate],
        *,
        scale: float,
        threshold: float,
        exclude_promo: bool = True,
    ) -> PackTemplateMatch | None:
        """在候选子包中取最高置信度匹配。"""
        filtered = self._filter_candidates(candidates, exclude_promo=exclude_promo)
        if not filtered:
            return None

        # 先确保模板都可用（避免中途缺模板导致漏算）
        self.prepare(filtered)

        template_names: list[str] = []
        candidate_by_template: dict[str, PackCandidate] = {}
        for c in filtered:
            template_name = self._pack_image_manager.get_template_name(c.booster_name)
            template_names.append(template_name)
            candidate_by_template[template_name] = c

        best = self._template_matcher.score_best_with_scale(
            screenshot,
            template_names,
            scale=scale,
            verbose=False,
            max_workers=10,
        )
        if not best:
            return None

        candidate = candidate_by_template.get(best.template_name)
        if not candidate:
            return None

        result = PackTemplateMatch(
            candidate=candidate,
            confidence=float(best.confidence),
            box=tuple(best.box),
        )
        return result if result.confidence >= threshold else None

    def end_session(self) -> None:
        """卸载本 session 新加载的 pack 模板。"""
        if not self._session_loaded_templates:
            return
        self._template_matcher.unload_templates(sorted(self._session_loaded_templates))
        self._session_loaded_templates.clear()

    # ==========================
    # 内部方法
    # ==========================

    def _filter_candidates(
        self,
        candidates: list[PackCandidate],
        *,
        exclude_promo: bool,
    ) -> list[PackCandidate]:
        out: list[PackCandidate] = []
        seen: set[str] = set()
        for c in candidates:
            if not c.booster_name or not c.set_code:
                continue
            if exclude_promo and c.set_code.upper().startswith("PROMO"):
                continue
            # 去重：同名子包只保留第一个
            if c.booster_name in seen:
                continue
            seen.add(c.booster_name)
            out.append(c)
        return out

    def _ensure_template_loaded(self, booster_name: str) -> bool:
        if not self._pack_image_manager.ensure_pack_ready(booster_name):
            return False

        template_name = self._pack_image_manager.get_template_name(booster_name)
        templates = getattr(self._template_matcher, "templates", {})
        if isinstance(templates, dict) and template_name in templates:
            return True

        loaded = bool(
            self._template_matcher.load_template(
                f"{template_name}.png",
                is_pack_template=True,
            )
        )
        if loaded:
            self._session_loaded_templates.add(template_name)
        return loaded

    # 注意：score_best_with_scale 的并行与线程安全由 TemplateMatcher 内部实现。


def build_pack_template_matcher(recognizer: Any) -> PackTemplateMatcher | None:
    """从 recognizer=(ocr_engine, template_matcher) 构建 PackTemplateMatcher。"""
    if not recognizer:
        return None
    try:
        _, template_matcher = recognizer
    except Exception:
        return None

    from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

    return PackTemplateMatcher(
        template_matcher=template_matcher,
        pack_image_manager=PackImageManager(),
    )
