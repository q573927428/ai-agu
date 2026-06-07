"""市场概览API路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.services.market_service import MarketService
from app.schemas.stock import ApiResponse

router = APIRouter(prefix="/market", tags=["市场"])


@router.get("/overview")
def get_market_overview(db: Session = Depends(get_db)) -> ApiResponse:
    """获取市场概览：上证/深证指数、涨跌家数、模型状态"""
    service = MarketService(db)
    overview = service.get_market_overview()
    return ApiResponse(data=overview)