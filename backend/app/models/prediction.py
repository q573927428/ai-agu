"""预测结果表"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, DateTime, Index
from sqlalchemy.sql import func
from .base import Base


class Prediction(Base):
    __tablename__ = "prediction"
    __table_args__ = (
        Index("idx_predict_date", "predict_date"),
        Index("idx_stock_predict_date", "stock_code", "predict_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    predict_date = Column(Date, nullable=False, comment="预测生成日期")
    target_date = Column(Date, nullable=False, comment="目标日期(T+20)")
    predicted_return = Column(DECIMAL(12, 6), comment="预测20日收益率")
    confidence = Column(DECIMAL(6, 4), comment="预测置信度")
    model_version = Column(String(200), comment="模型版本号")
    rank_score = Column(DECIMAL(12, 6), comment="排名分数(按预测收益率)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
