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
from concurrent.futures import ThreadPoolExecutor
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

    # 匹配线程数（经验值，避免调用方重复设置）
    _MAX_MATCH_WORKERS = 10

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
        best = self.score_best(
            screenshot,
            candidates,
            scale=scale,
            exclude_promo=exclude_promo,
        )
        if best is None:
            return None
        return best if best.confidence >= threshold else None

    def score_best(
        self,
        screenshot: Any,
        candidates: list[PackCandidate],
        *,
        scale: float,
        exclude_promo: bool = True,
    ) -> PackTemplateMatch | None:
        """计算候选子包的最高置信度（不做阈值裁决）。"""
        filtered = self._filter_candidates(candidates, exclude_promo=exclude_promo)
        if not filtered:
            return None

        # 先确保模板都可用（避免中途缺模板导致漏算）
        self.prepare(filtered)

        def _work(idx: int, c: PackCandidate):
            scored = self._score_one(
                screenshot,
                candidate=c,
                scale=scale,
            )
            if scored is None:
                return None
            return (idx, scored)

        best: tuple[int, PackTemplateMatch] | None = None
        with ThreadPoolExecutor(max_workers=self._MAX_MATCH_WORKERS) as ex:
            futures = [ex.submit(_work, i, c) for i, c in enumerate(filtered)]
            for f in futures:
                item = f.result()
                if item is None:
                    continue
                idx, scored = item
                if best is None:
                    best = (idx, scored)
                    continue
                best_idx, best_scored = best
                if scored.confidence > best_scored.confidence:
                    best = (idx, scored)
                elif scored.confidence == best_scored.confidence and idx < best_idx:
                    # 置信度一致时按候选顺序稳定选择
                    best = (idx, scored)

        return best[1] if best else None

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

    def _score_one(
        self,
        screenshot: Any,
        *,
        candidate: PackCandidate,
        scale: float,
    ) -> PackTemplateMatch | None:
        template_name = self._pack_image_manager.get_template_name(
            candidate.booster_name
        )
        match = self._template_matcher.find_with_scale(
            screenshot,
            template_name,
            scale=scale,
            threshold=self._SCORE_THRESHOLD_EPS,
            verbose=False,
        )
        if not match:
            return None

        return PackTemplateMatch(
            candidate=candidate,
            confidence=float(getattr(match, "confidence", 0.0)),
            box=tuple(getattr(match, "box")),
        )


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
