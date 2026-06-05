"""股票相关 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class StockBasicResponse(BaseModel):
    stock_code: str
    stock_name: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    area: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[date] = None
    is_active: Optional[int] = 1

    class Config:
        from_attributes = True


class StockDailyResponse(BaseModel):
    stock_code: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None
    float_mv: Optional[float] = None

    class Config:
        from_attributes = True


class StockPredictionResponse(BaseModel):
    predict_date: date
    predicted_return: Optional[float] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None

    class Config:
        from_attributes = True


class StockDetailResponse(BaseModel):
    basic: StockBasicResponse
    latest_daily: Optional[StockDailyResponse] = None
    latest_prediction: Optional[StockPredictionResponse] = None


class ApiResponse(BaseModel):
    code: int = 0
    data: Optional[dict] = None
    message: str = "success"