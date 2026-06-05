"""因子相关API路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.factor import FactorStore
from app.models.model_record import ModelRecord
from app.schemas.factor import FactorImportanceResponse, FactorImportance

router = APIRouter(prefix="/factors", tags=["因子"])


@router.get("/importance")
def get_factor_importance(db: Session = Depends(get_db)) -> FactorImportanceResponse:
    """获取因子重要性排名"""
    record = (
        db.query(ModelRecord)
        .filter(ModelRecord.is_active == 1)
        .order_by(ModelRecord.id.desc())
        .first()
    )

    if not record or not record.feature_importance_json:
        # 返回默认因子列表
        default_factors = [
            {"factor_name": "stock_roe_ttm", "importance": 0.0, "rank": 1},
            {"factor_name": "stock_momentum_20d", "importance": 0.0, "rank": 2},
        ]
        return FactorImportanceResponse(data=default_factors)

    features = record.feature_importance_json[:20]
    result = []
    for i, f in enumerate(features, 1):
        result.append(FactorImportance(
            factor_name=f.get("feature", "unknown"),
            importance=float(f.get("importance", 0)),
            rank=i,
        ))

    return FactorImportanceResponse(data=[r.model_dump() for r in result])