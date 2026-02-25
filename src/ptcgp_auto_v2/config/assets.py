# -*- coding: utf-8 -*-
"""静态资源相关常量与 URL 构造工具。"""

# 卡牌图片仓库与代理基础地址（统一单一来源）
CARD_IMAGE_REPO_BASE_URL = (
    "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images"
)
CARD_IMAGE_WSRV_BASE_URL = "https://wsrv.nl/?url="
CARD_IMAGE_CDN_ROOT_URL = "https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images"


def resolve_card_image_locale(lang: str) -> str:
    """根据语言解析图片资源 locale。"""
    normalized = (lang or "").lower()
    if normalized.startswith("zh"):
        return "zh-TW"
    return "en-US"


def build_card_image_bases(lang: str) -> dict[str, str]:
    """构造指定语言下的卡牌图片基础路径。"""
    image_locale = resolve_card_image_locale(lang)
    repo_cards_base = f"{CARD_IMAGE_REPO_BASE_URL}/{image_locale}/cards-by-set"
    return {
        "proxy_base_url": f"{CARD_IMAGE_WSRV_BASE_URL}{repo_cards_base}",
        "cdn_base_url": f"{CARD_IMAGE_CDN_ROOT_URL}/{image_locale}/cards-by-set",
    }


def build_card_image_urls(
    set_code: str,
    card_number: int,
    lang: str,
    width: int = 400,
) -> tuple[str, str]:
    """构造卡牌缩略图 PNG/WEBP 两个 URL。"""
    image_base_url = build_card_image_bases(lang)["proxy_base_url"]
    png_url = f"{image_base_url}/{set_code}/{card_number}.png&w={width}&output=png"
    webp_url = f"{image_base_url}/{set_code}/{card_number}.webp&w={width}&output=webp"
    return png_url, webp_url


def build_card_cdn_image_url(
    set_code: str,
    card_number: int,
    lang: str,
    ext: str = "png",
) -> str:
    """构造指定语言下的卡牌 CDN URL。"""
    cdn_base_url = build_card_image_bases(lang)["cdn_base_url"]
    return f"{cdn_base_url}/{set_code}/{card_number}.{ext}"
