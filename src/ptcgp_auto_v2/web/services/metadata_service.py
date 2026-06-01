import json
from typing import Any

from ptcgp_auto_v2.db.engine import get_session, session_scope
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)
from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore
from ptcgp_auto_v2.services.metadata_sync.poke52_localization_service import (
    Poke52LocalizationService,
)
from ptcgp_auto_v2.web.services.metadata_sync_service import (
    _METADATA_SYNC_PREVIEW_CACHE,
    build_default_check_context,
    check_sources,
    execute_sync,
    preview_sync,
)
from ptcgp_auto_v2.web.queries.metadata_queries import build_label_dict
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label


_SYNC_ACTION_MAP: dict[str, dict[str, Any]] = {
    "update_new_series": {
        "source": "flibustier",
        "mode": "supplement",
        "sync_kind": "update_new_series",
        "allowed_nodes": {"root"},
    },
    "update_data_supplement": {
        "source": "flibustier",
        "mode": "supplement",
        "sync_kind": "update_data",
        "allowed_nodes": {"root", "set", "pack", "card"},
    },
    "update_data_force": {
        "source": "flibustier",
        "mode": "force",
        "sync_kind": "update_data",
        "allowed_nodes": {"root", "set", "pack", "card"},
    },
    "update_chinese_supplement": {
        "source": "52poke",
        "mode": "supplement",
        "sync_kind": "update_chinese",
        "allowed_nodes": {"root", "set", "pack", "card"},
    },
    "update_chinese_force": {
        "source": "52poke",
        "mode": "force",
        "sync_kind": "update_chinese",
        "allowed_nodes": {"root", "set", "pack", "card"},
    },
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
    snapshot_id: str = "",
    current_action: str = "",
) -> dict:
    """构建元数据管理视图数据。"""
    from ptcgp_auto_v2.web.utils.i18n import resolve_label

    with session_scope() as session:
        repo = CardRepository(session)
        sets = repo.get_all_sets()
        packs = repo.get_all_packs()

        sets_data: list[dict[str, Any]] = []
        for item in sets:
            label_dict = build_label_dict(item.label_data)
            sets_data.append(
                {
                    "code": item.code,
                    "name": item.name,
                    "release_date": item.release_date,
                    "total_cards": item.total_cards,
                    "label_data": item.label_data,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "label_dict": label_dict,
                    "display_name": resolve_label(label_dict, fallback=item.name),
                }
            )

        packs_data: list[dict[str, Any]] = []
        for item in packs:
            label_dict = build_label_dict(item.label_data)
            packs_data.append(
                {
                    "name": item.name,
                    "set_code": item.set_code,
                    "label_data": item.label_data,
                    "image_url": item.image_url,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "label_dict": label_dict,
                    "display_name": resolve_label(label_dict, fallback=item.name),
                }
            )

        packs_by_set: dict[str, list[dict]] = {}
        for item in packs_data:
            set_code = item["set_code"]
            packs_by_set.setdefault(set_code, []).append(item)

        selected_context = _build_selected_context(
            repo=repo,
            packs_by_set=packs_by_set,
            selected_node_type=selected_node_type,
            selected_node_id=selected_node_id,
            selected_set_code=selected_set_code,
            selected_pack_name=selected_pack_name,
        )

    # 进入页面默认不触发远端请求，避免仅打开管理页就访问 ptcgp-assets/52poke。
    sync_check = build_default_check_context()
    snapshot_preview = _load_snapshot_preview(snapshot_id)

    available_actions = _get_actions_for_node(selected_context["selected_node_type"])
    available_action_cards = _build_action_cards(available_actions)
    normalized_action = _normalize_action_for_node(
        node_type=selected_context["selected_node_type"],
        action=current_action,
    )

    return {
        "ui_step": ui_step,
        "sets": sets_data,
        "packs_by_set": packs_by_set,
        "sync_check": sync_check,
        "snapshot_id": snapshot_id,
        "sync_preview": snapshot_preview or {},
        "sync_preview_json": json.dumps(snapshot_preview, ensure_ascii=False)
        if snapshot_preview
        else "",
        "current_action": normalized_action,
        "available_actions": available_actions,
        "available_action_cards": available_action_cards,
        **selected_context,
    }


def preview_metadata_sync(
    node_type: str,
    node_id: str,
    action: str,
    force_refresh: bool,
) -> dict[str, Any]:
    """生成元数据同步预览。"""
    resolved = resolve_sync_request(node_type=node_type, node_id=node_id, action=action)

    sets_data: dict[str, list[dict[str, Any]]] = {}
    cards_data: list[dict[str, Any]] = []
    extra_map: dict[tuple[str, int], dict[str, Any]] = {}
    if resolved["source"] == "flibustier":
        with session_scope() as session:
            flibustier_service = FlibustierSyncService(
                CardRepository(session),
                cache=_METADATA_REMOTE_CACHE,
            )
            sets_data, cards_data, extra_map = flibustier_service.fetch_remote_metadata(
                force_refresh=force_refresh
            )

    with session_scope() as session:
        repo = CardRepository(session)
        flibustier_service = FlibustierSyncService(repo, cache=_METADATA_REMOTE_CACHE)
        poke52_service = Poke52LocalizationService(cache=_METADATA_REMOTE_CACHE)
        return preview_sync(
            flibustier_service=flibustier_service,
            poke52_service=poke52_service,
            repo=repo,
            sync_kind=str(resolved["sync_kind"]),
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
    with session_scope() as session:
        repo = CardRepository(session)
        return execute_sync(
            flibustier_service=FlibustierSyncService(repo),
            repo=repo,
            snapshot_id=snapshot_id,
        )


def check_metadata_sources() -> dict[str, dict[str, int]]:
    """检查本地与远端源的基础统计。"""
    with session_scope() as session:
        repo = CardRepository(session)
        local_stats = repo.get_metadata_counts()

    temp_session = get_session()
    try:
        flibustier_service = FlibustierSyncService(
            CardRepository(temp_session),
            cache=_METADATA_REMOTE_CACHE,
        )
        flibustier_stats = {"sets": 0, "cards": 0}
        try:
            flibustier_stats = flibustier_service.fetch_remote_stats(
                force_refresh=False
            )
        except RuntimeError:
            pass
    finally:
        temp_session.close()

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
    allowed_nodes = resolved["allowed_nodes"]
    if normalized_node_type not in allowed_nodes:
        raise ValueError(f"动作 {action} 仅支持根节点")

    scope_level = _NODE_SCOPE_MAP[normalized_node_type]
    scope_value: str | None = None
    if normalized_node_type != "root":
        scope_value = (node_id or "").strip()
        if not scope_value:
            raise ValueError("节点标识不能为空")

    if normalized_action == "update_new_series":
        scope_level = "all"
        scope_value = None

    return {
        "source": str(resolved["source"]),
        "mode": str(resolved["mode"]),
        "sync_kind": str(resolved["sync_kind"]),
        "scope_level": scope_level,
        "scope_value": scope_value,
    }


def _build_selected_context(
    repo: CardRepository,
    packs_by_set: dict[str, list[dict[str, Any]]],
    selected_node_type: str,
    selected_node_id: str,
    selected_set_code: str,
    selected_pack_name: str,
) -> dict[str, Any]:
    """构建当前选中节点上下文"""
    node_type, node_id = _normalize_selected_node(selected_node_type, selected_node_id)
    set_code = (selected_set_code or "").strip()
    pack_name = (selected_pack_name or "").strip()
    card_key = ""
    node_type, node_id, set_code, pack_name, card_key = _resolve_selection_by_node(
        repo=repo,
        node_type=node_type,
        node_id=node_id,
        set_code=set_code,
        pack_name=pack_name,
    )
    set_code, pack_name = _sanitize_set_and_pack(
        packs_by_set=packs_by_set,
        set_code=set_code,
        pack_name=pack_name,
    )
    selected_pack_cards = _build_selected_pack_cards(
        repo=repo,
        set_code=set_code,
        pack_name=pack_name,
    )

    return {
        "selected_node_type": node_type,
        "selected_node_id": node_id,
        "selected_set_code": set_code,
        "selected_pack_name": pack_name,
        "selected_card_key": card_key,
        "selected_pack_cards": selected_pack_cards,
    }


def _normalize_selected_node(
    selected_node_type: str,
    selected_node_id: str,
) -> tuple[str, str]:
    """规范化节点类型和节点标识。"""
    node_type = (selected_node_type or "root").strip().lower()
    node_id = (selected_node_id or "all").strip()
    return node_type, node_id


def _resolve_selection_by_node(
    *,
    repo: CardRepository,
    node_type: str,
    node_id: str,
    set_code: str,
    pack_name: str,
) -> tuple[str, str, str, str, str]:
    """根据节点类型推导选中 set/pack/card。"""
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
    return node_type, node_id, set_code, pack_name, card_key


def _sanitize_set_and_pack(
    *,
    packs_by_set: dict[str, list[dict[str, Any]]],
    set_code: str,
    pack_name: str,
) -> tuple[str, str]:
    """清理非法 set/pack 选择。"""
    if set_code and set_code not in packs_by_set:
        return "", pack_name
    if set_code and pack_name:
        valid_pack_names = {item["name"] for item in packs_by_set.get(set_code, [])}
        if pack_name not in valid_pack_names:
            return set_code, ""
    return set_code, pack_name


def _build_selected_pack_cards(
    *,
    repo: CardRepository,
    set_code: str,
    pack_name: str,
) -> list[dict[str, Any]]:
    """构建当前卡包下的卡牌列表。"""
    if not set_code or not pack_name:
        return []
    from ptcgp_auto_v2.web.utils.i18n import resolve_label

    selected_pack_cards: list[dict[str, Any]] = []
    cards = repo.get_cards_by_pack(pack_name=pack_name, set_code=set_code)
    for card in cards:
        card_data = parse_json_label(card.data)
        localized_name = card_data.get("localized_name") if card_data else {}
        if isinstance(localized_name, dict):
            display_name = resolve_label(localized_name, fallback=card.name)
        else:
            display_name = resolve_label(card_data, fallback=card.name)

        selected_pack_cards.append(
            {
                "set_code": card.set_code,
                "number": card.number,
                "name": card.name,
                "display_name": display_name,
                "key": f"{card.set_code}-{card.number:03d}",
            }
        )
    return selected_pack_cards


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


def _load_snapshot_preview(snapshot_id: str) -> dict[str, Any] | None:
    """按 snapshot_id 读取缓存快照预览数据，供 Step2/Step3 透传展示。"""
    normalized_snapshot_id = (snapshot_id or "").strip()
    if not normalized_snapshot_id:
        return None
    cached_snapshot = _METADATA_SYNC_PREVIEW_CACHE.get(normalized_snapshot_id)
    if cached_snapshot is None or not isinstance(cached_snapshot, dict):
        return None

    payload = cached_snapshot.get("payload")
    summary = cached_snapshot.get("summary")
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(summary, dict):
        summary = {}

    items = cached_snapshot.get("items")
    if not isinstance(items, list):
        items = []

    return {
        "snapshot_id": normalized_snapshot_id,
        "summary": summary,
        "payload": payload,
        "items": items,
        "status": "previewed",
    }


def _default_action_for_node(node_type: str) -> str:
    """根据节点类型返回默认动作。"""
    if node_type == "root":
        return "update_new_series"
    return "update_data_supplement"


def _get_actions_for_node(node_type: str) -> list[str]:
    """根据节点类型返回可用动作。"""
    if node_type == "root":
        return [
            "update_new_series",
            "update_data_supplement",
            "update_data_force",
            "update_chinese_supplement",
            "update_chinese_force",
        ]
    if node_type in {"set", "pack", "card"}:
        return [
            "update_data_supplement",
            "update_data_force",
            "update_chinese_supplement",
            "update_chinese_force",
        ]
    return [
        "update_new_series",
        "update_data_supplement",
        "update_data_force",
        "update_chinese_supplement",
        "update_chinese_force",
    ]


def _normalize_action_for_node(node_type: str, action: str) -> str:
    """将动作归一为节点允许范围内的值。"""
    available_actions = _get_actions_for_node(node_type)
    normalized_action = (action or "").strip().lower()
    if normalized_action in available_actions:
        return normalized_action
    return _default_action_for_node(node_type)


def _build_action_cards(available_actions: list[str]) -> list[dict[str, Any]]:
    """将动作列表转换为卡片展示结构。"""
    cards: list[dict[str, Any]] = []
    if "update_new_series" in available_actions:
        cards.append(
            _build_action_card(
                title_key="metadata_action_update_new_series",
                title_fallback="更新新系列",
                buttons=[
                    {
                        "action": "update_new_series",
                        "label_key": "metadata_action_update_new_series",
                        "label_fallback": "更新新系列",
                        "mode": "supplement",
                    }
                ],
            )
        )

    data_buttons = _build_mode_buttons(
        available_actions=available_actions,
        supplement_action="update_data_supplement",
        force_action="update_data_force",
    )
    if data_buttons:
        cards.append(
            _build_action_card(
                title_key="metadata_action_update_data",
                title_fallback="更新数据",
                buttons=data_buttons,
            )
        )

    chinese_buttons = _build_mode_buttons(
        available_actions=available_actions,
        supplement_action="update_chinese_supplement",
        force_action="update_chinese_force",
    )
    if chinese_buttons:
        cards.append(
            _build_action_card(
                title_key="metadata_action_update_chinese",
                title_fallback="更新中文",
                buttons=chinese_buttons,
            )
        )
    return cards


def _build_action_card(
    *,
    title_key: str,
    title_fallback: str,
    buttons: list[dict[str, str]],
) -> dict[str, Any]:
    """构建动作卡片视图。"""
    return {
        "title_key": title_key,
        "title_fallback": title_fallback,
        "buttons": buttons,
    }


def _build_mode_buttons(
    *,
    available_actions: list[str],
    supplement_action: str,
    force_action: str,
) -> list[dict[str, str]]:
    """构建补充/覆盖动作按钮。"""
    buttons: list[dict[str, str]] = []
    if supplement_action in available_actions:
        buttons.append(
            {
                "action": supplement_action,
                "label_key": "metadata_mode_supplement",
                "label_fallback": "补充",
                "mode": "supplement",
            }
        )
    if force_action in available_actions:
        buttons.append(
            {
                "action": force_action,
                "label_key": "metadata_mode_force",
                "label_fallback": "覆盖",
                "mode": "force",
            }
        )
    return buttons
