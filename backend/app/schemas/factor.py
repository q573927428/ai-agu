"""因子相关 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class FactorValue(BaseModel):
    factor_name: str
    factor_value: float
    factor_type: Optional[str] = None


class FactorImportance(BaseModel):
    factor_name: str
    importance: float
    rank: int


class FactorResponse(BaseModel):
    stock_code: str
    trade_date: date
    factors: List[FactorValue]


class FactorImportanceResponse(BaseModel):
    code: int = 0
    data: Optional[List[FactorImportance]] = None
    message: str = "success"