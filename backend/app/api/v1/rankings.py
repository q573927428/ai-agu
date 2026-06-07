"""排名相关API路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.api.deps import get_db
from app.services.ranking_service import RankingService
from app.schemas.ranking import RankingResponse, RankingItem, FactorContribution
from app.models.prediction import Prediction

router = APIRouter(prefix="/rankings", tags=["排名"])


@router.get("")
def get_rankings(snapshot_date: Optional[str] = Query(None), db: Session = Depends(get_db)) -> RankingResponse:
    """获取TOP50排名"""
    service = RankingService(db)

    target_date = None
    if snapshot_date:
        target_date = date.fromisoformat(snapshot_date)

    rankings = service.get_top50(target_date)
    if not rankings:
        return RankingResponse(code=404, data=None, message="暂无排名数据")

    # 查询这些股票的最新预测置信度
    stock_codes = [r.stock_code for r in rankings]
    predictions = (
        db.query(Prediction)
        .filter(
            Prediction.stock_code.in_(stock_codes),
            Prediction.predict_date == (target_date or date.today()),
        )
        .all()
    )
    confidence_map = {p.stock_code: float(p.confidence) if p.confidence else None for p in predictions}

    items = []
    for r in rankings:
        top_factors = []
        if r.top_factors_json:
            for f in r.top_factors_json:
                top_factors.append(FactorContribution(**f))

        items.append(RankingItem(
            rank=r.rank_position,
            stock_code=r.stock_code,
            stock_name=r.stock_name or "",
            predicted_return=float(r.predicted_return or 0),
            confidence=confidence_map.get(r.stock_code),
            industry=r.industry,
            market_cap=float(r.market_cap or 0),
            top_factors=top_factors,
        ))

    snapshot_date_used = target_date or (rankings[0].snapshot_date if rankings else date.today())

    return RankingResponse(data={
        "date": str(snapshot_date_used),
        "rankings": [item.model_dump() for item in items],
        "total": len(items),
    })