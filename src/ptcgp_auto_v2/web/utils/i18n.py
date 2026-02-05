import json
import os
from typing import Dict, Any

from fastapi import Request


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


def get_translations(lang: str = "en") -> Dict[str, Any]:
    """按语言获取翻译字典（开发模式下每次刷新）。"""
    load_translations()
    return _translations.get(lang, _translations.get("en", {}))


def normalize_lang(lang: str) -> str:
    """校验语言参数并回退到默认值。"""
    load_translations()
    if lang in _translations:
        return lang
    normalized = lang.replace("-", "_").lower()
    for key in _translations:
        if key.lower() == normalized:
            return key
    if normalized.startswith("zh"):
        for candidate in ("zh_CN", "zh_TW", "zh_HK", "zh"):
            if candidate in _translations:
                return candidate
    if normalized.startswith("en") and "en" in _translations:
        return "en"
    return next(iter(_translations.keys()), "en")


def detect_lang(request: Request, explicit_lang: str | None) -> str:
    """根据显式参数、Cookie 与请求头识别语言。"""
    load_translations()
    if explicit_lang:
        return normalize_lang(explicit_lang)

    cookie_lang = request.cookies.get("ptcgp_lang")
    if cookie_lang:
        return normalize_lang(cookie_lang)

    header = request.headers.get("accept-language", "")
    for candidate in _parse_accept_language(header):
        normalized = normalize_lang(candidate)
        if normalized in _translations:
            return normalized

    return normalize_lang("en")


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
