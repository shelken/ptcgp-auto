import json
import os
from contextvars import ContextVar
from typing import Dict, Any, List, Optional

from fastapi import Request

from ptcgp_auto_v2.config.lang import (
    WEB_LANG_TO_DB_LABEL_KEYS,
    DEFAULT_LANG_KEY,
    resolve_localized_text,
)

# 全局请求上下文变量
_current_lang_ctx: ContextVar[Optional["LangContext"]] = ContextVar(
    "lang_ctx", default=None
)


_locales_dir: str | None = None
_translations: Dict[str, Dict[str, Any]] = {}


def init_i18n(locales_dir: str) -> None:
    """初始化多语言目录路径。"""
    global _locales_dir
    _locales_dir = locales_dir
    load_translations()


def load_translations() -> None:
    """加载所有语言资源到内存。"""
    if not _locales_dir:
        return
    if not os.path.exists(_locales_dir):
        return
    _translations.clear()
    for filename in os.listdir(_locales_dir):
        if filename.endswith(".json"):
            lang = filename.split(".")[0]
            with open(
                os.path.join(_locales_dir, filename), "r", encoding="utf-8"
            ) as file:
                _translations[lang] = json.load(file)


def get_translations(lang: str = DEFAULT_LANG_KEY) -> Dict[str, Any]:
    """按语言获取翻译字典（开发模式下每次刷新）。"""
    load_translations()
    return _translations.get(lang, _translations.get(DEFAULT_LANG_KEY, {}))


def resolve_lang_key(lang: str) -> str:
    """将任意语言输入解析为可用的翻译语言键。"""
    load_translations()
    if lang in _translations:
        return lang
    if DEFAULT_LANG_KEY in _translations:
        return DEFAULT_LANG_KEY
    return next(iter(_translations.keys()), DEFAULT_LANG_KEY)


def detect_lang(request: Request, explicit_lang: str | None) -> str:
    """根据显式参数、Cookie 与请求头识别语言。"""
    load_translations()
    if explicit_lang:
        return resolve_lang_key(explicit_lang)

    cookie_lang = request.cookies.get("ptcgp_lang")
    if cookie_lang:
        return resolve_lang_key(cookie_lang)

    header = request.headers.get("accept-language", "")
    for candidate in _parse_accept_language(header):
        if candidate in _translations:
            return candidate

    return resolve_lang_key(DEFAULT_LANG_KEY)


def _parse_accept_language(value: str) -> list[str]:
    """解析 Accept-Language 请求头。"""
    if not value:
        return []
    items: list[tuple[str, float]] = []
    for part in value.split(","):
        segment = part.strip()
        if not segment:
            continue
        lang_piece, *params = segment.split(";")
        lang = lang_piece.strip()
        q = 1.0
        for param in params:
            param = param.strip()
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 0.0
        items.append((lang, q))
    items.sort(key=lambda item: item[1], reverse=True)
    return [item[0] for item in items]


class LangContext:
    """语言上下文，在请求入口处统一构建，后续直接使用"""

    def __init__(self, web_lang: str):
        self.web_lang = web_lang
        # 标签语言候选列表（按优先级）
        self.label_candidates: List[str] = WEB_LANG_TO_DB_LABEL_KEYS.get(
            web_lang, WEB_LANG_TO_DB_LABEL_KEYS[DEFAULT_LANG_KEY]
        )

    def resolve_label(self, label_dict: Dict[str, Any], fallback: str = "") -> str:
        """从标签字典中按优先级解析展示名"""
        return resolve_localized_text(label_dict, self.web_lang, fallback=fallback)


def set_lang_context(web_lang: str) -> None:
    """在请求入口处设置全局语言上下文"""
    _current_lang_ctx.set(LangContext(web_lang))


def get_current_lang() -> str:
    """获取当前请求的语言（最底层使用）"""
    ctx = _current_lang_ctx.get()
    if ctx is None:
        return DEFAULT_LANG_KEY
    return ctx.web_lang


def get_current_i18n() -> tuple[str, Dict[str, Any]]:
    """获取当前请求语言与翻译字典（服务层统一入口）。"""
    current_lang = resolve_lang_key(get_current_lang())
    return current_lang, get_translations(current_lang)


def resolve_label(label_dict: Dict[str, Any], fallback: str = "") -> str:
    """解析标签（最底层使用，自动获取当前语言上下文）"""
    ctx = _current_lang_ctx.get()
    if ctx is None:
        ctx = LangContext(DEFAULT_LANG_KEY)
    return ctx.resolve_label(label_dict, fallback)


def resolve_label_json(raw: str | Dict[str, Any] | None, fallback: str = "") -> str:
    """从 JSON 文本/字典中解析本地化标签。"""
    return resolve_localized_text(raw, get_current_lang(), fallback=fallback)


def resolve_card_name_from_data(
    raw_data: str | Dict[str, Any] | None, fallback: str = ""
) -> str:
    """从卡牌 data 字段中解析当前语言名称。"""
    return resolve_localized_text(
        raw_data,
        get_current_lang(),
        fallback=fallback,
        localized_field="localized_name",
    )
