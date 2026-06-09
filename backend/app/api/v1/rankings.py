"""排名相关API路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, timedelta
from app.api.deps import get_db
from app.services.ranking_service import RankingService
from app.schemas.ranking import RankingResponse, RankingItem, FactorContribution
from app.models.prediction import Prediction
from app.models.stock_daily import StockDaily
from app.utils.date_utils import get_latest_trade_day
from loguru import logger

router = APIRouter(prefix="/rankings", tags=["排名"])


@router.get("")
def get_rankings(snapshot_date: Optional[str] = Query(None), db: Session = Depends(get_db)) -> RankingResponse:
    """获取TOP10排名"""
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
    target_date = pred_date + timedelta(days=1)  # 次日（T+1）

    # 查询预测日、次日的收盘价/涨跌幅，以及前日收盘价
    query_dates = [pred_date, target_date]

    # 如果预测日期没有行情数据（比如盘中运行），自动回退到上一个交易日
    daily_check = db.query(StockDaily.trade_date).filter(
        StockDaily.trade_date == pred_date
    ).first()
    if not daily_check:
        # 查找最近的有数据的交易日
        latest_trade = db.query(StockDaily.trade_date).distinct().order_by(
            StockDaily.trade_date.desc()
        ).first()
        if latest_trade:
            fallback_date = latest_trade[0]
            logger.warning(f"排名: {pred_date} 无行情数据，降级到最近交易日 {fallback_date}")
            pred_date = fallback_date
            target_date = pred_date + timedelta(days=1)
            query_dates = [pred_date, target_date]

    daily_rows = (
        db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.close, StockDaily.pre_close, StockDaily.pct_chg)
        .filter(
            StockDaily.stock_code.in_(stock_codes),
            StockDaily.trade_date.in_(query_dates),
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

        # 实际次日收益率（直接使用T+1日的涨跌幅）
        next_day_data = stock_actual.get(target_date, (None, None, None))
        actual_return_1d = next_day_data[2] / 100.0 if next_day_data[2] is not None else None

        items.append(RankingItem(
            rank=r.rank_position,
            stock_code=r.stock_code,
            stock_name=r.stock_name or "",
            predicted_return=float(r.predicted_return or 0),
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
