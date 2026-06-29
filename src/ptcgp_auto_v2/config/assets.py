# -*- coding: utf-8 -*-
"""静态资源相关常量与 URL 构造工具。"""

# 卡牌图片仓库与代理基础地址（统一单一来源）
CARD_IMAGE_REPO_BASE_URL = (
    "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images"
)
CARD_IMAGE_WSRV_BASE_URL = "https://wsrv.nl/?url="
CARD_IMAGE_CDN_ROOT_URL = "https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images"

# 预计算感知哈希 JSON 的 CDN 根地址（避免用户下载全量卡图本地算哈希）
CARD_HASH_CDN_ROOT_URL = (
    "https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/hashes"
)
# 哈希 JSON 算法版本；与 ptcgp-assets 仓库 scripts/generate_hashes.py 的 ALGO_VERSION 对齐
# 不一致时游戏端忽略该 JSON，回退到下载卡图本地算哈希
CARD_HASH_ALGO_VERSION = "v1"


def resolve_card_image_locale(lang: str) -> str:
    """根据语言解析图片资源 locale。"""
    # 单一映射：标准 web_lang -> 卡图资源目录 locale（ptcgp-assets 使用的目录名）
    mapping = {
        "zh_CN": "zh-TW",
        "en": "en-US",
    }
    return mapping.get(lang, mapping["zh_CN"])


def build_pack_image_url(sku_id: str, language: str = "en-US") -> str:
    """构造 ptcgp-assets 包封面 Raw URL。"""
    if not sku_id:
        raise ValueError("sku_id 不能为空")
    return f"{CARD_IMAGE_REPO_BASE_URL}/{language}/packs/{sku_id}.webp"


def build_card_image_bases(lang: str) -> dict[str, str]:
    """构造指定语言下的卡牌图片基础路径。"""
    image_locale = resolve_card_image_locale(lang)
    repo_cards_base = f"{CARD_IMAGE_REPO_BASE_URL}/{image_locale}/cards-by-set"
    return {
        "proxy_base_url": f"{CARD_IMAGE_WSRV_BASE_URL}{repo_cards_base}",
        "cdn_base_url": f"{CARD_IMAGE_CDN_ROOT_URL}/{image_locale}/cards-by-set",
        "misc_cdn_base_url": f"{CARD_IMAGE_CDN_ROOT_URL}/others",
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


def build_card_hash_json_url(set_code: str, lang: str = "zh_CN") -> str:
    """构造指定系列预计算哈希 JSON 的 CDN URL。

    locale 与卡图同源（zh_CN -> zh-TW），保证哈希来自与扫描下载相同的卡图。
    """
    image_locale = resolve_card_image_locale(lang)
    return f"{CARD_HASH_CDN_ROOT_URL}/{image_locale}/{set_code}.json"
