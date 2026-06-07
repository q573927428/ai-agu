"""排名快照表"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "rank_position", name="uk_snapshot_rank"),
        Index("idx_snapshot_date", "snapshot_date"),
        Index("idx_rank", "snapshot_date", "rank_position"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, comment="快照日期")
    rank_position = Column(Integer, nullable=False, comment="排名位置(1-50)")
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(50), comment="股票名称(冗余)")
    predicted_return = Column(DECIMAL(12, 6), comment="预测20日收益率")
    predicted_return_1d = Column(DECIMAL(12, 6), comment="预测1日收益率")
    industry = Column(String(50), comment="行业")
    market_cap = Column(DECIMAL(16, 2), comment="总市值")
    top_factors_json = Column(JSON, comment="TOP贡献因子JSON")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")