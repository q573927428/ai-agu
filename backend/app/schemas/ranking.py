"""排名相关 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class FactorContribution(BaseModel):
    name: str
    contribution: float


class RankingItem(BaseModel):
    rank: int
    stock_code: str
    stock_name: str
    predicted_return: float
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    top_factors: Optional[List[FactorContribution]] = None


class RankingData(BaseModel):
    date: date
    rankings: List[RankingItem]
    total: int = 50


class RankingResponse(BaseModel):
    code: int = 0
    data: Optional[RankingData] = None
    message: str = "success"