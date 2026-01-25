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
    AccountRepository,
    TaskPlanRepository,
    CardRepository,
    AccountPackConfigRepository
)
from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType

app = FastAPI(title="PTCGP Auto Web")

# Mount static files (css, js, images)
# Assumes src/ptcgp_auto_v2/web/static exists
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
    session: Session = Depends(get_fastapi_session)
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
    rarity_order = {'C':1, 'U':2, 'R':3, 'RR':4, 'AR':5, 'SR':6, 'SAR':7, 'UR':8, 'IM':9, 'S':10, 'SSR':11}
    rarities.sort(key=lambda x: rarity_order.get(x, 99))

    card_types = session.exec(select(distinct(Card.type)).order_by(Card.type)).all()
    card_types = [t for t in card_types if t]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rarities": rarities,
        "card_types": card_types,
        "t": t,
        "current_lang": lang
    })

@app.get("/api/records", response_class=HTMLResponse)
async def get_records(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    rarity: List[str] = Query(default=[]),
    card_type: List[str] = Query(default=[]),
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session)
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
        points_stmt = select(AccountPackPoint).where(col(AccountPackPoint.account_id).in_(account_ids))
        points_records = session.exec(points_stmt).all()
        for p in points_records:
            points_map[(p.account_id, p.series)] = p.points

    records_data = []
    for record in results:
        # Sort cards by position
        sorted_cards = sorted(record.cards, key=lambda c: c.position)

        # Determine layout class based on card count
        card_count = len(sorted_cards)
        layout_type = "grid-cols-2" # Default fallback

        if card_count == 6:
            layout_type = "layout-6" # 3 top, 3 bottom
        elif card_count == 5:
            layout_type = "layout-5" # 3 top, 2 bottom
        elif card_count == 4:
            layout_type = "layout-4" # 2 top, 2 bottom

        # 获取点数
        current_points = None
        if record.pack_code:
             current_points = points_map.get((record.account_id, record.pack_code))
        # 兼容旧数据：如果没有 pack_code 但 pack_type 有值且有点数记录
        elif record.pack_type and "/" in record.pack_type:
             series = record.pack_type.split("/")[0]
             current_points = points_map.get((record.account_id, series))

        records_data.append({
            "record": record,
            "cards": sorted_cards,
            "layout": layout_type,
            "account_name": record.account.nickname if record.account else t.get("unknown_account", "Unknown"),
            "opened_at": record.opened_at,
            "current_points": current_points,
            "series": record.pack_code or (record.pack_type.split("/")[0] if "/" in record.pack_type else "")
        })


    if not records_data:
        return "" # Stop HTMX polling

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
            "current_lang": lang
        }
    )

# --- Management APIs ---

@app.get("/management/accounts", response_class=HTMLResponse)
async def get_management_accounts(
    request: Request,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session)
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
            "current_lang": lang
        }
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
        {
            "request": request,
            "plans": plans,
            "t": t,
            "current_lang": lang
        }
    )

@app.get("/management/accounts/{account_id}/plans", response_class=HTMLResponse)
async def get_account_plans_modal(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session)
):
    """Render Edit Plans Modal for an Account"""
    t = get_translations(lang)

    # Direct query with session to avoid DetachedInstanceError with lazy loading
    statement = (
        select(Account)
        .where(Account.id == account_id)
        .options(
            selectinload(cast(Any, Account.task_plan)),
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

    # 确定当前关联
    current_primary_id = account.task_plan_id
    current_secondary_ids = [
        assoc.task_plan_id
        for assoc in account.task_plan_associations
        if assoc.is_active
    ]

    return templates.TemplateResponse(
        "partials/modals/edit_account_plans.html",
        {
            "request": request,
            "account": account,
            "all_plans": all_plans,
            "current_primary_id": current_primary_id,
            "current_secondary_ids": current_secondary_ids,
            "t": t,
            "current_lang": lang
        }
    )

@app.get("/management/plans/edit", response_class=HTMLResponse)
async def get_plan_edit_modal(
    request: Request,
    plan_id: Optional[int] = Query(None),
    lang: str = Query(default="en"),
):
    """Render Create/Edit Plan Modal"""
    t = get_translations(lang)
    repo = TaskPlanRepository() # Use repo for consistency if no relationships needed, or switch to session if needed

    plan = None
    if plan_id:
        plan = repo.get_by_id(plan_id)

    # 获取所有可用任务类型
    available_tasks = TaskRegistry.all_types()
    reset_types = [rt.value for rt in ResetType]

    return templates.TemplateResponse(
        "partials/modals/edit_plan.html",
        {
            "request": request,
            "plan": plan,
            "available_tasks": available_tasks,
            "reset_types": reset_types,
            "t": t,
            "current_lang": lang
        }
    )

@app.post("/api/accounts/{account_id}/plans")
async def update_account_plans(
    request: Request,
    account_id: int,
    lang: str = Query(default="en"),
    session: Session = Depends(get_fastapi_session),
):
    """Handle Account Plans Update"""
    form = await request.form()
    primary_plan_id = form.get("primary_plan_id")
    secondary_plan_ids = form.getlist("secondary_plan_ids") # Checkbox list

    repo = AccountRepository()

    # Update Primary
    if primary_plan_id:
        val = primary_plan_id
        if isinstance(val, str):
            repo.assign_task_plan(account_id, int(val))

    # Update Secondary
    # First, fetch existing active secondaries to know what to remove
    account = repo.get_by_id(account_id)
    if not account:
        # Should handle error, but for now just return
        return await get_management_accounts(request, lang=lang, session=session)

    if account.task_plan_associations:
        existing_ids = {assoc.task_plan_id for assoc in account.task_plan_associations if assoc.is_active}
    else:
        existing_ids = set()

    new_ids = set()
    for pid in secondary_plan_ids:
        if isinstance(pid, str) and pid.isdigit():
            new_ids.add(int(pid))

    # Add new
    for pid in new_ids - existing_ids:
        repo.add_secondary_plan(account_id, pid)

    # Remove old
    for pid in existing_ids - new_ids:
        repo.remove_secondary_plan(account_id, pid)

    # Return updated list or success message
    # For simplicity, we just trigger a reload of the accounts list
    # HTMX can target the table to refresh
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
    plan_id = form.get("plan_id")
    name = form.get("name")
    if not isinstance(name, str):
        name = ""
    description = form.get("description")
    if not isinstance(description, str):
        description = None

    # Construct task_types and configuration from dynamic form data
    # This part depends on how the frontend sends data.
    # For MVP, let's assume simple logic:
    # Form fields: tasks[open_pack][enabled], tasks[open_pack][reset_type], tasks[open_pack][interval]

    task_types = []
    configuration = {}

    for key in form:
        if key.startswith("task_enabled_"):
            task_type = key.replace("task_enabled_", "")
            task_types.append(task_type)

            # Check config
            r_type = form.get(f"task_reset_{task_type}")
            interval = form.get(f"task_interval_{task_type}")

            task_config = {}
            if r_type and r_type != "default": # Assume 'default' means use Task class default
                task_config["reset_type"] = r_type
                if r_type == "interval" and interval:
                    task_config["interval_seconds"] = int(interval)

            if task_config:
                configuration[task_type] = task_config

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
            configuration=json.dumps(configuration)
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
    request: Request,
    account_id: int,
    lang: str = Query(default="en")
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
    target_set = config.pack_code if config else (card_sets[0].code if card_sets else None)

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
            "current_lang": lang
        }
    )

@app.get("/partials/boosters-options", response_class=HTMLResponse)
async def get_boosters_options(
    request: Request,
    pack_code: str = Query(...)
):
    """HTMX Partial: Get booster options <option>...</option>"""
    repo = CardRepository()
    # pack_code IS the set_code in our context
    data = repo.get_packs_by_set(pack_code)
    boosters = []
    if data and pack_code in data:
        boosters = data[pack_code]["boosters"]

    return templates.TemplateResponse(
        "partials/options_boosters.html",
        {
            "request": request,
            "boosters": boosters
        }
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
    pack_code = form.get("pack_code")
    if not isinstance(pack_code, str):
        pack_code = ""
    booster_name = form.get("booster_name")
    if not isinstance(booster_name, str):
        booster_name = ""

    repo = AccountPackConfigRepository()

    # Create or Update logic
    # We construct an object, but upsert handles ID mapping
    config = AccountPackConfig(
        account_id=account_id,
        type="daily",
        pack_code=pack_code,
        booster_name=booster_name
    )
    repo.upsert(config)

    # Return updated account list to refresh the view
    response = await get_management_accounts(request, lang=lang, session=session)
    response.headers["HX-Trigger"] = "closeModal"
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
