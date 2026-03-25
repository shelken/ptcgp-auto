# -*- coding: utf-8 -*-
"""React 前端专用 API 聚合路由。"""

from __future__ import annotations

from fastapi import APIRouter

from ptcgp_auto_v2.web.routers import (
    react_api_accounts_plans,
    react_api_exchange_cards,
    react_api_friendships,
    react_api_metadata_daily_gift,
    react_api_notifications,
    react_api_owned_cards,
    react_api_records,
    react_api_resources_tasks,
)


router = APIRouter(prefix="/api/react", tags=["react-api"])
router.include_router(react_api_notifications.router)
router.include_router(react_api_records.router)
router.include_router(react_api_owned_cards.router)
router.include_router(react_api_exchange_cards.router)
router.include_router(react_api_accounts_plans.router)
router.include_router(react_api_resources_tasks.router)
router.include_router(react_api_metadata_daily_gift.router)
router.include_router(react_api_friendships.router)
