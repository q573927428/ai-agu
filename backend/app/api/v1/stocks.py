"""股票相关API路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from app.api.deps import get_db
from app.services.stock_service import StockService
from app.schemas.stock import StockBasicResponse, StockDetailResponse, ApiResponse

router = APIRouter(prefix="/stocks", tags=["股票"])


@router.get("/search")
def search_stocks(keyword: str = Query(..., min_length=1), db: Session = Depends(get_db)) -> ApiResponse:
    """搜索股票"""
    service = StockService(db)
    results = service.search_stocks(keyword)
    return ApiResponse(data={
        "results": [
            {
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "industry": s.industry,
            }
            for s in results
        ],
    })


@router.get("/{code}")
def get_stock_detail(code: str, db: Session = Depends(get_db)) -> ApiResponse:
    """获取股票详情"""
    service = StockService(db)
    detail = service.get_stock_detail(code)
    if not detail["basic"]:
        return ApiResponse(code=404, data=None, message="股票不存在")

    # 从因子表获取 pe_ttm/pb/turnover_rate
    from app.models.factor import FactorStore
    factors = (
        db.query(FactorStore)
        .filter(FactorStore.stock_code == code)
        .order_by(FactorStore.trade_date.desc())
        .first()
    )

    return ApiResponse(data={
        "basic": {
            "stock_code": detail["basic"].stock_code,
            "stock_name": detail["basic"].stock_name,
            "industry": detail["basic"].industry,
            "area": detail["basic"].area,
            "market": detail["basic"].market,
            "list_date": str(detail["basic"].list_date) if detail["basic"].list_date else None,
        },
        "latest_daily": {
            "close": float(detail["latest_daily"].close) if detail["latest_daily"] else None,
            "open": float(detail["latest_daily"].open) if detail["latest_daily"] else None,
            "high": float(detail["latest_daily"].high) if detail["latest_daily"] else None,
            "low": float(detail["latest_daily"].low) if detail["latest_daily"] else None,
            "pre_close": float(detail["latest_daily"].pre_close) if detail["latest_daily"] else None,
            "volume": int(detail["latest_daily"].volume) if detail["latest_daily"] else None,
            "amount": float(detail["latest_daily"].amount) if detail["latest_daily"] else None,
            "pct_chg": float(detail["latest_daily"].pct_chg) if detail["latest_daily"] else None,
            "pe_ttm": float(factors.stock_pe_ttm) if factors and factors.stock_pe_ttm is not None else None,
            "pb": float(factors.stock_pb) if factors and factors.stock_pb is not None else None,
            "turnover_rate": float(factors.stock_turnover_rate_5d) if factors and factors.stock_turnover_rate_5d is not None else None,
        } if detail["latest_daily"] else None,
        "latest_prediction": {
            "predict_date": str(detail["latest_prediction"].predict_date) if detail["latest_prediction"] else None,
            "predicted_return": float(detail["latest_prediction"].predicted_return) if detail["latest_prediction"] else None,
            "predicted_return_1d": float(detail["latest_prediction"].predicted_return_1d) if detail["latest_prediction"] and detail["latest_prediction"].predicted_return_1d else None,
            "confidence": float(detail["latest_prediction"].confidence) if detail["latest_prediction"] else None,
        } if detail["latest_prediction"] else None,
    })


@router.get("/{code}/factors")
def get_stock_factors(code: str, db: Session = Depends(get_db)) -> ApiResponse:
    """获取股票因子数据"""
    from app.models.factor import FactorStore
    factors = (
        db.query(FactorStore)
        .filter(FactorStore.stock_code == code)
        .order_by(FactorStore.trade_date.desc())
        .first()
    )
    if not factors:
        return ApiResponse(code=404, data=None, message="因子数据不存在")

    factor_list = []
    for col in FactorStore.__table__.columns:
        if col.name in ("id", "stock_code", "trade_date", "created_at"):
            continue
        val = getattr(factors, col.name)
        if val is not None:
            factor_list.append({"name": col.name, "value": float(val)})

    return ApiResponse(data={
        "stock_code": code,
        "trade_date": str(factors.trade_date),
        "factors": factor_list,
    })


@router.get("/{code}/financial")
def get_stock_financial(code: str, db: Session = Depends(get_db)) -> ApiResponse:
    """获取股票财务数据（利润表 + 资产负债表 + 财务指标）"""
    from app.models.income import Income
    from app.models.balancesheet import Balancesheet
    from app.models.fina_indicator import FinaIndicator

    # 利润表（最近5期）
    income_records = (
        db.query(Income)
        .filter(Income.stock_code == code, Income.report_type == 1)
        .order_by(Income.end_date.desc())
        .limit(5)
        .all()
    )
    # 资产负债表（最近5期）
    bs_records = (
        db.query(Balancesheet)
        .filter(Balancesheet.stock_code == code, Balancesheet.report_type == 1)
        .order_by(Balancesheet.end_date.desc())
        .limit(5)
        .all()
    )
    # 财务指标（最近5期）
    ind_records = (
        db.query(FinaIndicator)
        .filter(FinaIndicator.stock_code == code)
        .order_by(FinaIndicator.end_date.desc())
        .limit(5)
        .all()
    )

    return ApiResponse(data={
        "stock_code": code,
        "income": [
            {
                "end_date": str(r.end_date),
                "revenue": float(r.revenue) if r.revenue else None,
                "net_profit": float(r.net_profit) if r.net_profit else None,
                "eps": float(r.eps) if r.eps else None,
            }
            for r in income_records
        ],
        "balancesheet": [
            {
                "end_date": str(r.end_date),
                "total_assets": float(r.total_assets) if r.total_assets else None,
                "total_liab": float(r.total_liab) if r.total_liab else None,
                "total_equity": float(r.total_equity) if r.total_equity else None,
            }
            for r in bs_records
        ],
        "indicators": [
            {
                "end_date": str(r.end_date),
                "roe": float(r.roe) if r.roe else None,
                "roa": float(r.roa) if r.roa else None,
                "gross_margin": float(r.gross_margin) if r.gross_margin else None,
                "net_margin": float(r.net_margin) if r.net_margin else None,
                "debt_ratio": float(r.debt_ratio) if r.debt_ratio else None,
            }
            for r in ind_records
        ],
    })


@router.get("/{code}/prediction")
def get_stock_prediction(code: str, db: Session = Depends(get_db)) -> ApiResponse:
    """获取股票预测历史"""
    from app.models.prediction import Prediction
    records = (
        db.query(Prediction)
        .filter(Prediction.stock_code == code)
        .order_by(Prediction.predict_date.desc())
        .limit(20)
        .all()
    )
    return ApiResponse(data={
        "stock_code": code,
        "predictions": [
            {
                "predict_date": str(r.predict_date),
                "predicted_return": float(r.predicted_return) if r.predicted_return else None,
                "predicted_return_1d": float(r.predicted_return_1d) if r.predicted_return_1d else None,
                "confidence": float(r.confidence) if r.confidence else None,
            }
            for r in records
        ],
    })