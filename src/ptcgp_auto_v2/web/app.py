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
from typing import Annotated, List, Optional, Dict
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
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository
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
        query = query.join(PackRecord.cards).join(PackCard.card)
        
        if rarity:
            query = query.where(col(Card.rarity).in_(rarity))
        
        if card_type:
            query = query.where(col(Card.type).in_(card_type))
            
    # Apply pagination
    query = query.offset(offset).limit(page_size)
    
    results = session.exec(query).all()
    
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
            
        records_data.append({
            "record": record,
            "cards": sorted_cards,
            "layout": layout_type,
            "account_name": record.account.nickname if record.account else t.get("unknown_account", "Unknown"),
            "opened_at": record.opened_at
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
    # 使用 AccountRepository.get_all 已经包含 eager load
    # 为了在 Web App 中使用，我们需要确保 session 正确。
    # Repository 默认创建新 session，这里为了复用 FastAPI 依赖注入的 session
    # 我们可能需要重构 Repository 或直接使用 session 查询。
    # 鉴于 Repository 内部使用了 `with Session(get_engine())`，它是独立的。
    # 这在并发低时没问题。
    accounts = repo.get_all()

    return templates.TemplateResponse(
        "partials/account_list.html",
        {
            "request": request,
            "accounts": accounts,
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
            selectinload(Account.task_plan),
            selectinload(Account.task_plan_associations).selectinload(
                AccountTaskPlan.task_plan
            ),
        )
    )
    account = session.exec(statement).first()

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
):
    """Handle Account Plans Update"""
    form = await request.form()
    primary_plan_id = form.get("primary_plan_id")
    secondary_plan_ids = form.getlist("secondary_plan_ids") # Checkbox list

    repo = AccountRepository()

    # Update Primary
    if primary_plan_id:
        repo.assign_task_plan(account_id, int(primary_plan_id))

    # Update Secondary
    # First, fetch existing active secondaries to know what to remove
    account = repo.get_by_id(account_id)
    existing_ids = {assoc.task_plan_id for assoc in account.task_plan_associations if assoc.is_active}
    new_ids = {int(pid) for pid in secondary_plan_ids}

    # Add new
    for pid in new_ids - existing_ids:
        repo.add_secondary_plan(account_id, pid)

    # Remove old
    for pid in existing_ids - new_ids:
        repo.remove_secondary_plan(account_id, pid)

    # Return updated list or success message
    # For simplicity, we just trigger a reload of the accounts list
    # HTMX can target the table to refresh
    return await get_management_accounts(request, lang=lang)

@app.post("/api/plans")
async def save_plan(
    request: Request,
    lang: str = Query(default="en"),
):
    """Handle Plan Create/Update"""
    form = await request.form()
    plan_id = form.get("plan_id")
    name = form.get("name")
    description = form.get("description")

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

    repo = TaskPlanRepository()

    if plan_id:
        plan = repo.get_by_id(int(plan_id))
        plan.name = name
        plan.description = description
        plan.task_types = json.dumps(task_types)
        plan.configuration = json.dumps(configuration)
        repo.update(plan)
    else:
        plan = TaskPlan(
            name=name,
            description=description,
            task_types=json.dumps(task_types),
            configuration=json.dumps(configuration)
        )
        repo.create(plan)

    return await get_management_plans(request, lang=lang)

@app.delete("/api/plans/{plan_id}")
async def delete_plan(
    request: Request,
    plan_id: int,
    lang: str = Query(default="en"),
):
    repo = TaskPlanRepository()
    repo.delete(plan_id)
    return await get_management_plans(request, lang=lang)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
