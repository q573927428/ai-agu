"""v1 路由聚合"""
from fastapi import APIRouter
from app.api.v1 import stocks, rankings, factors, market

router = APIRouter(prefix="/api/v1")

router.include_router(stocks.router)
router.include_router(rankings.router)
router.include_router(factors.router)
router.include_router(market.router)
