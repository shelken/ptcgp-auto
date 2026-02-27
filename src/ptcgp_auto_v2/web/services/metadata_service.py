import json
from typing import Any

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.db.repositories.metadata_sync_snapshot_repository import (
    MetadataSyncSnapshotRepository,
)
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)
from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore
from ptcgp_auto_v2.services.metadata_sync.poke52_localization_service import (
    Poke52LocalizationService,
)
from ptcgp_auto_v2.web.services.metadata_sync_service import (
    build_default_check_context,
    check_sources,
    execute_sync,
    preview_sync,
)
from ptcgp_auto_v2.web.queries.metadata_queries import build_label_dict
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


_SYNC_ACTION_MAP: dict[str, dict[str, str]] = {
    "structure_supplement": {"source": "flibustier", "mode": "supplement"},
    "structure_force": {"source": "flibustier", "mode": "force"},
    "sync_supplement": {"source": "full", "mode": "supplement"},
    "sync_force": {"source": "full", "mode": "force"},
    "localize_supplement": {"source": "52poke", "mode": "supplement"},
    "localize_force": {"source": "52poke", "mode": "force"},
}

_NODE_SCOPE_MAP: dict[str, str] = {
    "root": "all",
    "set": "set",
    "pack": "pack",
    "card": "card",
}


# 远端请求缓存（Web进程内）
_METADATA_REMOTE_CACHE = TTLCacheStore(ttl_seconds=21600)


def build_metadata_context(
    ui_step: int = 1,
    selected_node_type: str = "root",
    selected_node_id: str = "all",
    selected_set_code: str = "",
    selected_pack_name: str = "",
) -> dict:
    """构建元数据管理视图数据。语言在最底层自动处理"""
    from ptcgp_auto_v2.web.utils.i18n import resolve_label

    current_lang, t = get_current_i18n()
    repo = CardRepository()
    sets = repo.get_all_sets()
    packs = repo.get_all_packs()

    sets_data = []
    for item in sets:
        data = item.model_dump()
        data["label_dict"] = build_label_dict(item.label_data)
        data["display_name"] = resolve_label(data["label_dict"], fallback=item.name)
        sets_data.append(data)

    packs_data = []
    for item in packs:
        data = item.model_dump()
        data["label_dict"] = build_label_dict(item.label_data)
        data["display_name"] = resolve_label(data["label_dict"], fallback=item.name)
        packs_data.append(data)

    packs_by_set: dict[str, list[dict]] = {}
    for item in packs_data:
        set_code = item["set_code"]
        packs_by_set.setdefault(set_code, []).append(item)

    selected_context = _build_selected_context(
        repo=repo,
        sets_data=sets_data,
        packs_by_set=packs_by_set,
        selected_node_type=selected_node_type,
        selected_node_id=selected_node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )

    # 进入页面默认不触发远端请求，避免仅打开管理页就访问 flibustier/52poke。
    sync_check = build_default_check_context()

    return {
        "ui_step": ui_step,
        "sets": sets_data,
        "packs_by_set": packs_by_set,
        "sync_check": sync_check,
        "lang_key": current_lang,
        "current_action": _default_action_for_node(
            node_type=selected_context["selected_node_type"]
        ),
        **selected_context,
        "t": t,
        "current_lang": current_lang,
    }


def update_set_label(code: str, label_zh: str) -> None:
    """更新卡包系列中文名。"""
    repo = CardRepository()
    card_set = repo.get_set_by_code(code)
    if not card_set:
        return
    labels = parse_json_label(card_set.label_data)
    labels[_get_zh_label_key()] = label_zh
    repo.update_set_label(code, json.dumps(labels, ensure_ascii=False))


def update_pack_label(name: str, label_zh: str) -> None:
    """更新补充包中文名。"""
    repo = CardRepository()
    pack = repo.get_pack_by_name(name)
    if not pack:
        return
    labels = parse_json_label(pack.label_data)
    labels[_get_zh_label_key()] = label_zh
    repo.update_pack_label(name, json.dumps(labels, ensure_ascii=False))


def preview_metadata_sync(
    node_type: str,
    node_id: str,
    action: str,
    force_refresh: bool,
) -> dict[str, Any]:
    """生成元数据同步预览。"""
    resolved = resolve_sync_request(node_type=node_type, node_id=node_id, action=action)

    repo = CardRepository()
    flibustier_service = FlibustierSyncService(repo, cache=_METADATA_REMOTE_CACHE)
    poke52_service = Poke52LocalizationService(cache=_METADATA_REMOTE_CACHE)
    snapshot_repo = MetadataSyncSnapshotRepository()

    sets_data: dict[str, list[dict[str, Any]]] = {}
    cards_data: list[dict[str, Any]] = []
    extra_map: dict[tuple[str, int], dict[str, Any]] = {}
    if resolved["source"] in {"flibustier", "full"}:
        sets_data, cards_data, extra_map = flibustier_service.fetch_remote_metadata(
            force_refresh=force_refresh
        )

    return preview_sync(
        snapshot_repo=snapshot_repo,
        flibustier_service=flibustier_service,
        poke52_service=poke52_service,
        source=resolved["source"],
        mode=resolved["mode"],
        scope_level=resolved["scope_level"],
        scope_value=resolved["scope_value"],
        force_refresh=force_refresh,
        remote_sets_data=sets_data,
        remote_cards_data=cards_data,
        remote_extra_map=extra_map,
    )


def execute_metadata_sync(snapshot_id: str) -> dict[str, Any]:
    """执行元数据同步。"""
    repo = CardRepository()
    return execute_sync(
        snapshot_repo=MetadataSyncSnapshotRepository(),
        flibustier_service=FlibustierSyncService(repo),
        snapshot_id=snapshot_id,
    )


def check_metadata_sources() -> dict[str, dict[str, int]]:
    """检查本地与远端源的基础统计。"""
    repo = CardRepository()
    local_stats = {
        "sets": len(repo.get_all_sets()),
        "packs": len(repo.get_all_packs()),
        "cards": sum(
            len(repo.get_cards_by_set(item.code)) for item in repo.get_all_sets()
        ),
    }

    flibustier_service = FlibustierSyncService(repo, cache=_METADATA_REMOTE_CACHE)
    flibustier_stats = {"sets": 0, "cards": 0}
    try:
        flibustier_stats = flibustier_service.fetch_remote_stats(force_refresh=False)
    except RuntimeError:
        pass

    poke52_service = Poke52LocalizationService(cache=_METADATA_REMOTE_CACHE)
    poke52_stats = {"series": 0, "packs": 0}
    try:
        poke52_stats = poke52_service.fetch_remote_stats()
    except RuntimeError:
        pass

    return check_sources(
        local_stats=local_stats,
        flibustier_stats=flibustier_stats,
        poke52_stats=poke52_stats,
    )


def resolve_sync_request(
    node_type: str, node_id: str, action: str
) -> dict[str, str | None]:
    """将节点动作解析为同步请求参数。"""
    normalized_node_type = (node_type or "root").strip().lower()
    normalized_action = (action or "").strip().lower()

    if normalized_action not in _SYNC_ACTION_MAP:
        raise ValueError(f"不支持的同步动作: {action}")
    if normalized_node_type not in _NODE_SCOPE_MAP:
        raise ValueError(f"不支持的节点类型: {node_type}")

    resolved = _SYNC_ACTION_MAP[normalized_action]
    scope_level = _NODE_SCOPE_MAP[normalized_node_type]
    scope_value: str | None = None
    if normalized_node_type != "root":
        scope_value = (node_id or "").strip()
        if not scope_value:
            raise ValueError("节点标识不能为空")

    return {
        "source": resolved["source"],
        "mode": resolved["mode"],
        "scope_level": scope_level,
        "scope_value": scope_value,
    }


def _build_selected_context(
    repo: CardRepository,
    sets_data: list[dict[str, Any]],
    packs_by_set: dict[str, list[dict[str, Any]]],
    selected_node_type: str,
    selected_node_id: str,
    selected_set_code: str,
    selected_pack_name: str,
) -> dict[str, Any]:
    """构建当前选中节点上下文"""
    node_type = (selected_node_type or "root").strip().lower()
    node_id = (selected_node_id or "all").strip()

    set_code = (selected_set_code or "").strip()
    pack_name = (selected_pack_name or "").strip()
    card_key = ""

    if node_type == "set":
        set_code = node_id
    elif node_type == "pack":
        pack_name = node_id
        pack_obj = repo.get_pack_by_name(pack_name)
        if pack_obj:
            set_code = pack_obj.set_code
    elif node_type == "card":
        card_key = node_id
        parsed = _parse_card_key(card_key)
        if parsed:
            set_code, _ = parsed
        if pack_name == "":
            pack_name = _guess_pack_name_by_card(repo, card_key)
    elif node_type != "root":
        node_type = "root"
        node_id = "all"

    if set_code and set_code not in packs_by_set:
        set_code = ""
    if set_code and pack_name:
        valid_pack_names = {item["name"] for item in packs_by_set.get(set_code, [])}
        if pack_name not in valid_pack_names:
            pack_name = ""

    selected_pack_cards: list[dict[str, Any]] = []
    if set_code and pack_name:
        from ptcgp_auto_v2.web.utils.i18n import resolve_label
        cards = repo.get_cards_by_pack(pack_name=pack_name, set_code=set_code)
        selected_pack_cards = [
            {
                "set_code": card.set_code,
                "number": card.number,
                "name": card.name,
                "display_name": resolve_label(card.data, fallback=card.name) if card.data else card.name,
                "key": f"{card.set_code}-{card.number:03d}",
            }
            for card in cards
        ]

    return {
        "selected_node_type": node_type,
        "selected_node_id": node_id,
        "selected_set_code": set_code,
        "selected_pack_name": pack_name,
        "selected_card_key": card_key,
        "selected_pack_cards": selected_pack_cards,
    }


def _parse_card_key(card_key: str) -> tuple[str, int] | None:
    """解析卡牌节点 key。"""
    if "-" not in card_key:
        return None
    set_code, raw_num = card_key.split("-", 1)
    try:
        number = int(raw_num)
    except (TypeError, ValueError):
        return None
    return set_code, number


def _guess_pack_name_by_card(repo: CardRepository, card_key: str) -> str:
    """根据卡牌 key 推断一个卡包名。"""
    parsed = _parse_card_key(card_key)
    if not parsed:
        return ""
    set_code, number = parsed
    card = repo.get_card_by_set_and_number(set_code, number)
    if card is None or card.id is None:
        return ""
    pack_names = repo.get_card_pack_names(card.id)
    if not pack_names:
        return ""
    return pack_names[0]


def _default_action_for_node(node_type: str) -> str:
    """根据节点类型返回默认动作。"""
    if node_type == "card":
        return "structure_force"
    if node_type == "pack":
        return "structure_supplement"
    if node_type == "set":
        return "sync_supplement"
    return "sync_supplement"


def _get_zh_label_key() -> str:
    """获取中文对应的标签键（通过 map 查找）"""
    from ptcgp_auto_v2.config.constants import WEB_LANG_ZH, WEB_LANG_TO_DB_LABEL_KEYS
    return WEB_LANG_TO_DB_LABEL_KEYS[WEB_LANG_ZH][0]
