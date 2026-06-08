"""排名相关API路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta
from app.api.deps import get_db
from app.services.ranking_service import RankingService
from app.schemas.ranking import RankingResponse, RankingItem, FactorContribution
from app.models.prediction import Prediction
from app.models.stock_daily import StockDaily

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

    # 判断实际数据日期（可能因降级而与请求日期不同）
    actual_date = rankings[0].snapshot_date

    # 查询这些股票的最新预测置信度（用实际数据日期关联）
    stock_codes = [r.stock_code for r in rankings]
    predictions = (
        db.query(Prediction)
        .filter(
            Prediction.stock_code.in_(stock_codes),
            Prediction.predict_date == actual_date,
        )
        .all()
    )
    confidence_map = {p.stock_code: float(p.confidence) if p.confidence else None for p in predictions}

    # 批量查询这些股票的实际行情数据（用于对比）
    pred_date = actual_date
    next_date = pred_date + timedelta(days=1)
    target_20d_date = pred_date + timedelta(days=20)

    # 查询预测日、次日、T+20的收盘价/涨跌幅，以及前日收盘价
    daily_rows = (
        db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.close, StockDaily.pre_close, StockDaily.pct_chg)
        .filter(
            StockDaily.stock_code.in_(stock_codes),
            StockDaily.trade_date.in_([pred_date, next_date, target_20d_date]),
        )
        .all()
    )

    # 构建 stock_code -> {trade_date: (close, pre_close, pct_chg)} 映射
    actual_map: dict[str, dict] = {}
    for sc, td, close, pre_close, pct in daily_rows:
        actual_map.setdefault(sc, {})[td] = (
            float(close) if close else None,
            float(pre_close) if pre_close else None,
            float(pct) if pct else None,
        )

    items = []
    for r in rankings:
        top_factors = []
        if r.top_factors_json:
            for f in r.top_factors_json:
                top_factors.append(FactorContribution(**f))

        # 计算实际收益率
        stock_actual = actual_map.get(r.stock_code, {})

        # 收盘价
        today_data = stock_actual.get(pred_date, (None, None, None))
        close_price = today_data[0]
        pre_close_price = today_data[1]

        # 实际20日收益率
        current_close = close_price
        target_close = stock_actual.get(target_20d_date, (None, None, None))[0]
        actual_return_20d = None
        if current_close and target_close and current_close > 0:
            actual_return_20d = round((target_close / current_close - 1), 4)

        # 实际次日涨跌幅
        next_day_data = stock_actual.get(next_date, (None, None, None))
        next_day_pct = next_day_data[2]
        actual_return_1d = round(next_day_pct / 100.0, 4) if next_day_pct is not None else None

        items.append(RankingItem(
            rank=r.rank_position,
            stock_code=r.stock_code,
            stock_name=r.stock_name or "",
            predicted_return=float(r.predicted_return or 0),
            predicted_return_1d=float(r.predicted_return_1d or 0) if r.predicted_return_1d else None,
            actual_return_20d=actual_return_20d,
            actual_return_1d=actual_return_1d,
            confidence=confidence_map.get(r.stock_code),
            industry=r.industry,
            market_cap=float(r.market_cap or 0),
            close_price=close_price,
            pre_close_price=pre_close_price,
            top_factors=top_factors,
        ))

    return RankingResponse(data={
        "date": str(actual_date),
        "rankings": [item.model_dump() for item in items],
        "total": len(items),
    })
