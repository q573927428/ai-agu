"""财务指标模型 — 对应 Tushare Pro fina_indicator 接口"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class FinaIndicator(Base):
    """财务指标（核心量化因子来源）"""
    __tablename__ = "fina_indicator"
    __table_args__ = (
        UniqueConstraint("stock_code", "end_date", name="uk_stock_date"),
        Index("idx_end_date", "end_date"),
        Index("idx_stock_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期")

    # ── 盈利能力 ──
    roe = Column(DECIMAL(10, 4), comment="净资产收益率(%)")
    roa = Column(DECIMAL(10, 4), comment="总资产收益率(%)")
    gross_margin = Column(DECIMAL(16, 4), comment="销售毛利率(%)")
    net_margin = Column(DECIMAL(10, 4), comment="销售净利率(%)")
    eps = Column(DECIMAL(10, 4), comment="每股收益")

    # ── 成长能力 (同比) ──
    revenue_yoy = Column(DECIMAL(10, 4), comment="营收同比增长率(%)")
    net_profit_yoy = Column(DECIMAL(10, 4), comment="净利润同比增长率(%)")
    oper_cf_yoy = Column(DECIMAL(10, 4), comment="经营活动现金流同比增长率(%)")
    roe_yoy = Column(DECIMAL(10, 4), comment="ROE同比增长率(%)")

    # ── 运营能力 ──
    asset_turnover = Column(DECIMAL(10, 4), comment="总资产周转率")
    receiv_turn = Column(DECIMAL(10, 4), comment="应收账款周转率")

    # ── 偿债能力 ──
    debt_ratio = Column(DECIMAL(10, 4), comment="资产负债率(%)")
    current_ratio = Column(DECIMAL(10, 4), comment="流动比率")
    quick_ratio = Column(DECIMAL(10, 4), comment="速动比率")

    # ── 每股指标 ──
    bps = Column(DECIMAL(10, 4), comment="每股净资产")
    cashflow_ps = Column(DECIMAL(10, 4), comment="每股经营活动现金流")

    # ── 系统字段 ──
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")