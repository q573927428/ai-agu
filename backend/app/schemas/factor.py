"""因子相关 Pydantic 模型"""
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import date


class FactorValue(BaseModel):
    """单个因子值"""

    factor_name: str = Field(..., min_length=1, description="因子名称")
    factor_value: float = Field(..., description="因子数值，必须为有限数")
    factor_type: Optional[str] = None

    @field_validator("factor_value")
    @classmethod
    def validate_factor_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("factor_value must be finite")
        return value


class FactorImportance(BaseModel):
    """因子重要性"""

    factor_name: str = Field(..., min_length=1, description="因子名称")
    importance: float = Field(..., ge=0, description="重要性分数")
    rank: int = Field(..., ge=1, description="排名，从1开始")


class FactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_code: str
    trade_date: date
    factors: List[FactorValue]


class FactorImportanceResponse(BaseModel):
    code: int = 0
    data: Optional[List[FactorImportance]] = None
    message: str = "success"