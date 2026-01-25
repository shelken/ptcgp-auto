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
from typing import Annotated, List, Optional, Dict
from datetime import datetime
import os
import math

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.models.pack_record import PackRecord
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.db.models.card import Card

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
    for t in card_type:
        next_page_url += f"&card_type={t}"

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
