import sys
import os
import json

# Add the src directory to sys.path to allow importing ptcgp_auto_v2
# This allows running the script directly from anywhere
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(src_dir)

from fastapi import FastAPI, Depends, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select, desc, col, distinct
from sqlalchemy.orm import selectinload
from typing import Annotated, List, Optional, Dict, cast, Any
from datetime import datetime
import os
import math

# FastAPI app setup
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.models.pack_record import PackRecord
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.models.task_plan import TaskPlan
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.models.account_pack_point import AccountPackPoint
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    AccountRepository,
    TaskPlanRepository,
    CardRepository,
    AccountPackConfigRepository,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType

# 导入任务模块以触发注册
import ptcgp_auto_v2.tasks

from ptcgp_auto_v2.db.models.card import Pack

# 表单处理工具
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string, parse_json_label
from ptcgp_auto_v2.web.utils.element_utils import normalize_elements

app = FastAPI(title="PTCGP Auto Web")

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# i18n Logic
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = {}


def load_translations():
    global translations
    if not os.path.exists(locales_dir):
        return
    for filename in os.listdir(locales_dir):
        if filename.endswith(".json"):
            lang = filename.split(".")[0]
            with open(os.path.join(locales_dir, filename), "r", encoding="utf-8") as f:
                translations[lang] = json.load(f)


load_translations()


def get_translations(lang: str = "en") -> Dict:
    # Reload translations on every request for development
    # This allows i18n changes to take effect without server restart
    load_translations()
    return translations.get(lang, translations.get("en", {}))


# Add custom filters to Jinja2
def format_datetime(value: datetime):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


templates.env.filters["datetime"] = format_datetime


@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    # Determine language (priority: query param > defaults to en)
    if lang not in translations:
        lang = "en"

    t = get_translations(lang)

    # Fetch distinct rarities and types for filters
    rarities = session.exec(select(distinct(Card.rarity)).order_by(Card.rarity)).all()
    # Cleanup rarities: filter out None
    rarities = [r for r in rarities if r]

    # Custom sort order for rarity if possible, otherwise alphabetical
    rarity_order = {
        "C": 1,
        "U": 2,
        "R": 3,
        "RR": 4,
        "AR": 5,
        "SR": 6,
        "SAR": 7,
        "UR": 8,
        "IM": 9,
        "S": 10,
        "SSR": 11,
    }
    rarities.sort(key=lambda x: rarity_order.get(x, 99))

    card_types = session.exec(select(distinct(Card.type)).order_by(Card.type)).all()
    card_types = [t for t in card_types if t]

    elements = session.exec(select(distinct(Card.element)).order_by(Card.element)).all()
    elements = normalize_elements(elements)

    card_repo = CardRepository()
    card_sets = card_repo.get_all_sets()
    packs = card_repo.get_all_packs()

    lang_key = "zh" if lang.startswith("zh") else "en"
    sets_data = [
        {
            "code": s.code,
            "label": parse_json_label(s.label_data),
        }
        for s in card_sets
    ]
    packs_data = [
        {
            "name": p.name,
            "set_code": p.set_code,
            "label": parse_json_label(p.label_data),
        }
        for p in packs
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "rarities": rarities,
            "card_types": card_types,
            "elements": elements,
            "card_sets": sets_data,
            "packs": packs_data,
            "lang_key": lang_key,
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/api/owned-cards", response_class=HTMLResponse)
async def get_owned_cards(
    request: Request,
    page: int = 0,
    page_size: int = 60,
    rarity: List[str] = Query(default=[]),
    card_type: List[str] = Query(default=[]),
    set_code: List[str] = Query(default=[]),
    pack_name: List[str] = Query(default=[]),
    element: List[str] = Query(default=[]),
    lang: str = Query(default="en"),
):
    t = get_translations(lang)
    repo = AccountCardRepository()
    items = repo.list_owned_cards(
        page=page,
        page_size=page_size,
        rarities=rarity,
        card_types=card_type,
        set_codes=set_code,
        pack_names=pack_name,
        elements=element,
    )

    if not items and page > 0:
        return ""

    next_page_url = f"/api/owned-cards?page={page + 1}&lang={lang}"
    for r in rarity:
        next_page_url += f"&rarity={r}"
    for c_type in card_type:
        next_page_url += f"&card_type={c_type}"
    for s_code in set_code:
        next_page_url += f"&set_code={s_code}"
    for p_name in pack_name:
        next_page_url += f"&pack_name={p_name}"
    for el in element:
        next_page_url += f"&element={el}"

    return templates.TemplateResponse(
        "partials/owned_card_list.html",
        {
            "request": request,
            "items": items,
            "next_page_url": next_page_url,
            "page": page,
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/api/owned-cards/modal", response_class=HTMLResponse)
async def get_owned_card_modal(
    request: Request,
    card_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    t = get_translations(lang)
    card = session.get(Card, card_id)
    if not card:
        return HTMLResponse(
            t.get("owned_cards_not_found", "Card not found"), status_code=404
        )

    repo = AccountCardRepository()
    data = repo.get_owned_card_accounts(card_id)
    return templates.TemplateResponse(
        "partials/modals/owned_card_detail.html",
        {
            "request": request,
            "card": card,
            "accounts": data["accounts"],
            "total_accounts": data["total_accounts"],
            "total_count": data["total_count"],
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/api/records", response_class=HTMLResponse)
async def get_records(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    rarity: List[str] = Query(default=[]),
    card_type: List[str] = Query(default=[]),
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """
    Fetch pack records with pagination for HTMX infinite scroll.
    Returns HTML fragment of record cards.
    """
    t = get_translations(lang)
    offset = page * page_size

    # Base Query: Select PackRecords
    query = select(PackRecord).distinct().order_by(desc(PackRecord.opened_at))

    # Join necessary tables if filtering
    if rarity or card_type:
        query = query.join(cast(Any, PackRecord.cards)).join(cast(Any, PackCard.card))

        if rarity:
            query = query.where(col(Card.rarity).in_(rarity))

        if card_type:
            query = query.where(col(Card.type).in_(card_type))

    # Apply pagination
    query = query.offset(offset).limit(page_size)

    results = session.exec(query).all()

    # Pre-fetch metadata for localization
    card_repo = CardRepository()
    all_sets = card_repo.get_all_sets()
    all_packs = card_repo.get_all_packs()

    # Build lookup maps: code/name -> label_dict
    sets_map = {}
    for s in all_sets:
        sets_map[s.code] = parse_json_label(s.label_data)

    packs_map = {}
    for p in all_packs:
        packs_map[p.name] = parse_json_label(p.label_data)

    # 批量获取相关的 Pack Points (使用 account_id 和 pack_code 关联)
    # 收集需要查询的组合 (account_id, series)
    target_combinations = set()
    for r in results:
        if r.account_id and r.pack_code:
            target_combinations.add((r.account_id, r.pack_code))

    points_map = {}
    if target_combinations:
        # 这里为了简单，先查询出涉及账号的所有点数，或者如果SQLModel支持复杂IN查询更好
        # 考虑到点数数据量不大，我们查询所有涉及账号的所有点数记录
        account_ids = {c[0] for c in target_combinations}
        points_stmt = select(AccountPackPoint).where(
            col(AccountPackPoint.account_id).in_(account_ids)
        )
        points_records = session.exec(points_stmt).all()
        for p in points_records:
            points_map[(p.account_id, p.series)] = p.points

    records_data = []
    # Determine target language key (e.g., 'zh' for 'zh_CN', 'en' for 'en')
    lang_key = "zh" if lang.startswith("zh") else "en"

    for record in results:
        # Sort cards by position
        sorted_cards = sorted(record.cards, key=lambda c: c.position)

        # Determine layout class based on card count
        card_count = len(sorted_cards)
        layout_type = "layout-3"  # Default fallback (3 cards in a row)

        if card_count == 6:
            layout_type = "layout-6"  # 3 top, 3 bottom
        elif card_count == 5:
            layout_type = "layout-5"  # 3 top, 2 bottom
        elif card_count == 4:
            layout_type = "layout-4"  # 2 top, 2 bottom
        elif card_count == 3:
            layout_type = "layout-3"  # 3 in a row

        # 获取点数
        current_points = None
        series_code = ""
        if record.pack_code:
            current_points = points_map.get((record.account_id, record.pack_code))
            series_code = record.pack_code
        # 兼容旧数据：如果没有 pack_code 但 pack_type 有值且有点数记录
        elif record.pack_type and "/" in record.pack_type:
            series = record.pack_type.split("/")[0]
            current_points = points_map.get((record.account_id, series))
            series_code = series

        # Localize Pack Info
        # Set Name
        set_name_display = series_code
        if series_code in sets_map:
            set_name_display = (
                sets_map[series_code].get(lang_key)
                or sets_map[series_code].get("en")
                or series_code
            )

        # Pack Name
        pack_name_display = record.pack_name or ""
        if record.pack_name in packs_map:
            pack_name_display = (
                packs_map[record.pack_name].get(lang_key)
                or packs_map[record.pack_name].get("en")
                or record.pack_name
            )

        records_data.append(
            {
                "record": record,
                "cards": sorted_cards,
                "layout": layout_type,
                "account_name": record.account.nickname
                if record.account
                else t.get("unknown_account", "Unknown"),
                "opened_at": record.opened_at,
                "current_points": current_points,
                "series": series_code,
                "set_name_display": set_name_display,
                "pack_name_display": pack_name_display,
            }
        )

    if not records_data:
        return ""  # Stop HTMX polling

    # Pass filters back to pagination URL
    # Build query string manually or via helper
    next_page_url = f"/api/records?page={page + 1}&lang={lang}"
    for r in rarity:
        next_page_url += f"&rarity={r}"
    for c_type in card_type:
        next_page_url += f"&card_type={c_type}"

    return templates.TemplateResponse(
        "partials/record_list.html",
        {
            "request": request,
            "records": records_data,
            "next_page_url": next_page_url,
            "t": t,
            "current_lang": lang,
        },
    )


# --- Management APIs ---


@app.get("/management/accounts", response_class=HTMLResponse)
async def get_management_accounts(
    request: Request,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Render Accounts Management Table"""
    t = get_translations(lang)
    repo = AccountRepository()
    accounts = repo.get_all()

    # Fetch Pack Configs for display
    # We query all 'daily' configs to map them to accounts
    config_stm = select(AccountPackConfig).where(AccountPackConfig.type == "daily")
    all_configs = session.exec(config_stm).all()
    pack_configs_map = {c.account_id: c for c in all_configs}

    return templates.TemplateResponse(
        "partials/account_list.html",
        {
            "request": request,
            "accounts": accounts,
            "pack_configs": pack_configs_map,
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/management/plans", response_class=HTMLResponse)
async def get_management_plans(
    request: Request,
    lang: str = Query(default="en"),
):
    """Render Task Plans Management Table"""
    t = get_translations(lang)
    repo = TaskPlanRepository()
    plans = repo.get_all()

    return templates.TemplateResponse(
        "partials/plan_list.html",
        {"request": request, "plans": plans, "t": t, "current_lang": lang},
    )


@app.get("/management/accounts/{account_id}/edit", response_class=HTMLResponse)
async def get_account_edit_modal(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Render Edit Account Details Modal"""
    t = get_translations(lang)
    repo = AccountRepository()
    account = repo.get_by_id(account_id)

    if not account:
        return HTMLResponse("Account not found", status_code=404)

    return templates.TemplateResponse(
        "partials/modals/edit_account.html",
        {"request": request, "account": account, "t": t, "current_lang": lang},
    )


@app.get("/management/plans/edit", response_class=HTMLResponse)
async def get_plan_edit_modal(
    request: Request,
    plan_id: Optional[int] = Query(None),
    lang: str = Query(default="en"),
):
    """Render Create/Edit Plan Modal"""
    t = get_translations(lang)
    repo = TaskPlanRepository()

    plan = None
    if plan_id:
        plan = repo.get_by_id(plan_id)

    # 获取所有可用任务类型
    available_tasks = TaskRegistry.all_types()
    reset_types = [rt.value for rt in ResetType]

    # 按 plan.task_types_list 顺序排序（已启用的任务在前）
    if plan and plan.task_types_list:
        # 已启用的任务按 plan.task_types_list 顺序
        ordered_enabled_tasks = [
            t for t in plan.task_types_list if t in available_tasks
        ]
        # 未启用的任务保持注册顺序
        ordered_disabled_tasks = [
            t for t in available_tasks if t not in plan.task_types_list
        ]
        ordered_tasks = ordered_enabled_tasks + ordered_disabled_tasks
    else:
        # 新建 plan，保持注册顺序
        ordered_tasks = available_tasks

    return templates.TemplateResponse(
        "partials/modals/edit_plan.html",
        {
            "request": request,
            "plan": plan,
            "available_tasks": ordered_tasks,  # 使用排序后的任务列表
            "reset_types": reset_types,
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/management/accounts/{account_id}/plans", response_class=HTMLResponse)
async def get_account_plans_modal(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Render Edit Plans Modal for an Account"""
    t = get_translations(lang)

    # Direct query with session to avoid DetachedInstanceError with lazy loading
    statement = (
        select(Account)
        .where(Account.id == account_id)
        .options(
            selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                cast(Any, AccountTaskPlan.task_plan)
            ),
        )
    )
    account = session.exec(statement).first()

    if not account:
        return HTMLResponse("Account not found", status_code=404)

    plan_repo = TaskPlanRepository()
    all_plans = plan_repo.get_all()

    # 整理当前关联的计划 (按优先级降序)
    current_assocs = sorted(account.task_plan_associations, key=lambda x: -x.priority)

    # 获取已关联的 plan_id 集合
    associated_plan_ids = {assoc.task_plan_id for assoc in current_assocs}

    # 整理未关联的计划 (Available Plans)
    available_plans = [p for p in all_plans if p.id not in associated_plan_ids]

    return templates.TemplateResponse(
        "partials/modals/edit_account_plans.html",
        {
            "request": request,
            "account": account,
            "current_assocs": current_assocs,
            "available_plans": available_plans,
            "t": t,
            "current_lang": lang,
        },
    )


@app.post("/api/accounts/{account_id}/plans")
async def update_account_plans(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
):
    """Handle Account Plans Update (JSON)"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return HTMLResponse("Invalid JSON", status_code=400)

    # Data format: [{ "plan_id": 1, "is_active": True }, ...] (Ordered list)
    # Convert to format required by repository: [{ "plan_id": 1, "is_active": True, "priority": 100 }, ...]

    repo = AccountRepository()
    plans_data = []

    # 按照列表顺序分配优先级，第一个优先级最高 (例如 100, 90, 80...)
    base_priority = 100
    for i, item in enumerate(data):
        plan_id = item.get("plan_id")
        is_active = item.get("is_active", True)

        if plan_id:
            priority = max(0, base_priority - (i * 10))
            plans_data.append(
                {"plan_id": int(plan_id), "is_active": is_active, "priority": priority}
            )

    repo.update_plan_associations(account_id, plans_data)

    # Return success - usually to trigger a client-side reload or close modal
    # Since we use fetch(), we return a JSON response or just 200 OK
    # To keep HTMX happy if we were using it, we might return partials,
    # but here we are called via fetch(). We can just return {"status": "ok"}
    return {"status": "ok"}


@app.post("/api/accounts/{account_id}/details")
async def update_account_details(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Handle Account Details Update (Nickname, Remark)"""
    form = await request.form()
    nickname = safe_get_string(form, "nickname") or ""
    remark = safe_get_string(form, "remark") or ""

    repo = AccountRepository()
    account = repo.get_by_id(account_id)

    if account:
        account.nickname = nickname
        account.remark = remark
        repo.update(account)

    response = await get_management_accounts(request, lang=lang, session=session)
    response.headers["HX-Trigger"] = "closeModal"
    return response


@app.post("/api/plans")
async def save_plan(
    request: Request,
    lang: str = Query(default="en"),
):
    """Handle Plan Create/Update"""
    form = await request.form()
    plan_id = safe_get_string(form, "plan_id")
    name = safe_get_string(form, "name") or ""
    description = safe_get_string(form, "description")

    # Construct task_types and configuration from dynamic form data
    # This part depends on how the frontend sends data.
    # For MVP, let's assume simple logic:
    # Form fields: tasks[open_pack][enabled], tasks[open_pack][reset_type], tasks[open_pack][interval]

    # Check for task_order field (JSON array with sorted task types)
    task_order_str = safe_get_string(form, "task_order")
    task_order = []
    if task_order_str:
        try:
            task_order = json.loads(task_order_str)
        except (json.JSONDecodeError, TypeError):
            task_order = []

    configuration = {}
    enabled_task_types = set()

    # First pass: collect enabled tasks and their configurations
    for key in form:
        if key.startswith("task_enabled_"):
            task_type = key.replace("task_enabled_", "")
            enabled_task_types.add(task_type)

            # Check config
            r_type = safe_get_string(form, f"task_reset_{task_type}")
            interval = safe_get_string(form, f"task_interval_{task_type}")

            task_config = {}
            if (
                r_type and isinstance(r_type, str) and r_type != "default"
            ):  # Assume 'default' means use Task class default
                task_config["reset_type"] = r_type
                if r_type == "interval" and interval and isinstance(interval, str):
                    try:
                        task_config["interval_seconds"] = int(interval)
                    except ValueError:
                        pass

            if task_config:
                configuration[task_type] = task_config

    # Build task_types list: use task_order if available, otherwise fallback to form order
    if task_order:
        # Filter to only include enabled tasks, preserving the order from task_order
        task_types = [t for t in task_order if t in enabled_task_types]
    else:
        # Fallback: iterate form in order (may not preserve DOM order)
        task_types = []
        for key in form:
            if key.startswith("task_enabled_"):
                task_type = key.replace("task_enabled_", "")
                task_types.append(task_type)

    # Debug log for configuration issues
    print(f"DEBUG: Processed configuration: {configuration}")

    repo = TaskPlanRepository()

    plan = None
    if plan_id:
        val = plan_id
        if isinstance(val, str) and val.isdigit():
            plan = repo.get_by_id(int(val))
        if plan:
            plan.name = name
            plan.description = description
            plan.task_types = json.dumps(task_types)
            # Ensure we are saving the dict as a JSON string
            plan.configuration = json.dumps(configuration)

            # Explicitly check if update returns True
            if not repo.update(plan):
                # 如果 plan_id 是 UploadFile，这里也不会触发，因为前面有 isinstance 检查
                # 为了让 pyright 开心，我们可以将 plan_id 强制转换为 str 或者使用 val
                pid_str = val if isinstance(val, str) else str(plan_id)
                print(f"ERROR: Failed to update plan {pid_str}")

    # Check if we need to create a new one (plan was None, meaning either no ID provided or ID invalid/not found)
    if not plan:
        plan = TaskPlan(
            name=name,
            description=description,
            task_types=json.dumps(task_types),
            configuration=json.dumps(configuration),
        )
        repo.create(plan)

    response = await get_management_plans(request, lang=lang)
    response.headers["HX-Trigger"] = "closeModal"
    return response


@app.delete("/api/plans/{plan_id}")
async def delete_plan(
    request: Request,
    plan_id: int,
    lang: str = Query(default="en"),
):
    repo = TaskPlanRepository()
    repo.delete(plan_id)
    return await get_management_plans(request, lang=lang)


# --- Metadata Management APIs ---


@app.get("/management/metadata", response_class=HTMLResponse)
async def get_management_metadata(
    request: Request,
    lang: str = Query(default="en"),
):
    """Render Metadata Management Page"""
    t = get_translations(lang)
    repo = CardRepository()
    sets = repo.get_all_sets()
    packs = repo.get_all_packs()

    # 解析 label_data 并转换为字典供模板使用
    sets_data = []
    for s in sets:
        data = s.model_dump()
        try:
            data["label_dict"] = json.loads(s.label_data) if s.label_data else {}
        except:
            data["label_dict"] = {}
        sets_data.append(data)

    packs_data = []
    for p in packs:
        data = p.model_dump()
        try:
            data["label_dict"] = json.loads(p.label_data) if p.label_data else {}
        except:
            data["label_dict"] = {}
        packs_data.append(data)

    # Group packs by set_code
    packs_by_set = {}
    for p in packs_data:
        set_code = p["set_code"]
        if set_code not in packs_by_set:
            packs_by_set[set_code] = []
        packs_by_set[set_code].append(p)

    return templates.TemplateResponse(
        "partials/metadata_list.html",
        {
            "request": request,
            "sets": sets_data,
            "packs_by_set": packs_by_set,
            "t": t,
            "current_lang": lang,
        },
    )


@app.post("/api/metadata/set/{code}/label")
async def update_set_label(
    request: Request,
    code: str,
    lang: str = Query(default="en"),
):
    """Update Card Set Label (zh)"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh")

    repo = CardRepository()
    card_set = repo.get_set_by_code(code)

    if card_set:
        labels = parse_json_label(card_set.label_data)
        labels["zh"] = label_zh
        repo.update_set_label(code, json.dumps(labels, ensure_ascii=False))

    # Return refreshed view
    return await get_management_metadata(request, lang=lang)


@app.post("/api/metadata/pack/{name}/label")
async def update_pack_label(
    request: Request,
    name: str,
    lang: str = Query(default="en"),
):
    """Update Pack Label (zh)"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh")

    repo = CardRepository()
    pack = repo.get_pack_by_name(name)

    if pack:
        labels = parse_json_label(pack.label_data)
        labels["zh"] = label_zh
        repo.update_pack_label(name, json.dumps(labels, ensure_ascii=False))

    return await get_management_metadata(request, lang=lang)


# --- Pack Config APIs ---


@app.get("/api/card-sets")
async def get_card_sets():
    """Get all card sets"""
    repo = CardRepository()
    sets = repo.get_all_sets()
    return [{"code": s.code, "name": s.name} for s in sets]


@app.get("/api/card-sets/{set_code}/boosters")
async def get_set_boosters(set_code: str):
    """Get boosters for a specific card set"""
    repo = CardRepository()
    data = repo.get_packs_by_set(set_code)
    if not data or set_code not in data:
        return []
    return data[set_code]["boosters"]


@app.get("/management/accounts/{account_id}/pack-config", response_class=HTMLResponse)
async def get_account_pack_config_modal(
    request: Request, account_id: int, lang: str = Query(default="en")
):
    """Render Pack Config Modal"""
    t = get_translations(lang)
    config_repo = AccountPackConfigRepository()
    card_repo = CardRepository()

    # Get current config (default to 'daily' type)
    config = config_repo.get_by_account_and_type(account_id, "daily")

    # Get all Card Sets for dropdown
    card_sets = card_repo.get_all_sets()

    # Get current boosters if a set is selected
    current_boosters = []
    # If config exists, load its set's boosters
    target_set = (
        config.pack_code if config else (card_sets[0].code if card_sets else None)
    )

    if target_set:
        data = card_repo.get_packs_by_set(target_set)
        if data and target_set in data:
            current_boosters = data[target_set]["boosters"]

    return templates.TemplateResponse(
        "partials/modals/edit_pack_config.html",
        {
            "request": request,
            "account_id": account_id,
            "config": config,
            "card_sets": card_sets,
            "current_boosters": current_boosters,
            "t": t,
            "current_lang": lang,
        },
    )


@app.get("/partials/boosters-options", response_class=HTMLResponse)
async def get_boosters_options(request: Request, pack_code: str = Query(...)):
    """HTMX Partial: Get booster options <option>...</option>"""
    repo = CardRepository()
    # pack_code IS the set_code in our context
    data = repo.get_packs_by_set(pack_code)
    boosters = []
    if data and pack_code in data:
        boosters = data[pack_code]["boosters"]

    return templates.TemplateResponse(
        "partials/options_boosters.html", {"request": request, "boosters": boosters}
    )


@app.post("/api/accounts/{account_id}/pack-config")
async def save_account_pack_config(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Save Account Pack Config"""
    form = await request.form()
    pack_code = safe_get_string(form, "pack_code") or ""
    booster_name = safe_get_string(form, "booster_name") or ""

    repo = AccountPackConfigRepository()

    # Create or Update logic
    # We construct an object, but upsert handles ID mapping
    config = AccountPackConfig(
        account_id=account_id,
        type="daily",
        pack_code=pack_code,
        booster_name=booster_name,
    )
    repo.upsert(config)

    # Return updated account list to refresh the view
    response = await get_management_accounts(request, lang=lang, session=session)
    response.headers["HX-Trigger"] = "closeModal"
    return response


if __name__ == "__main__":
    # 初始化数据库
    from ptcgp_auto_v2.db.connection import get_database

    get_database()

    # 初始化 Settings
    from ptcgp_auto_v2.config.settings import Settings, set_settings

    settings = Settings()
    set_settings(settings)
    settings.configure_logging()

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
