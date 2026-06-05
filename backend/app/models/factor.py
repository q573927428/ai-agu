"""因子存储表（宽表设计）"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class FactorStore(Base):
    __tablename__ = "factor_store"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_code_date"),
        Index("idx_date", "trade_date"),
        Index("idx_stock_date", "stock_code", "trade_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    trade_date = Column(Date, nullable=False)

    # 宏观因子 (15)
    macro_gdp_yoy = Column(DECIMAL(12, 6))
    macro_cpi_yoy = Column(DECIMAL(12, 6))
    macro_ppi_yoy = Column(DECIMAL(12, 6))
    macro_pmi = Column(DECIMAL(12, 6))
    macro_m2_yoy = Column(DECIMAL(12, 6))
    macro_shibor_on = Column(DECIMAL(12, 6))
    macro_shibor_1m = Column(DECIMAL(12, 6))
    macro_usdcny = Column(DECIMAL(12, 6))
    macro_hgt = Column(DECIMAL(12, 6))
    macro_sgt = Column(DECIMAL(12, 6))
    macro_north_flow = Column(DECIMAL(12, 6))
    macro_margin_balance = Column(DECIMAL(12, 6))
    macro_us_y3m = Column(DECIMAL(12, 6))
    macro_us_y2y = Column(DECIMAL(12, 6))
    macro_us_y10y = Column(DECIMAL(12, 6))

    # 市场因子 (10)
    market_idx_return_5d = Column(DECIMAL(12, 6))
    market_idx_return_20d = Column(DECIMAL(12, 6))
    market_idx_volatility_20d = Column(DECIMAL(12, 6))
    market_turnover_ma5 = Column(DECIMAL(12, 6))
    market_advance_decline_ratio = Column(DECIMAL(12, 6))
    market_volume_ratio = Column(DECIMAL(12, 6))
    market_breadth_20d = Column(DECIMAL(12, 6))
    market_vix_proxy = Column(DECIMAL(12, 6))
    market_style_momentum = Column(DECIMAL(12, 6))
    market_style_value = Column(DECIMAL(12, 6))

    # 行业因子 (10)
    industry_return_5d = Column(DECIMAL(12, 6))
    industry_return_20d = Column(DECIMAL(12, 6))
    industry_return_volatility = Column(DECIMAL(12, 6))
    industry_pe_percentile = Column(DECIMAL(12, 6))
    industry_pb_percentile = Column(DECIMAL(12, 6))
    industry_roe_median = Column(DECIMAL(12, 6))
    industry_momentum_rank = Column(DECIMAL(12, 6))
    industry_reversal_signal = Column(DECIMAL(12, 6))
    industry_fund_flow = Column(DECIMAL(12, 6))
    industry_dispersion = Column(DECIMAL(12, 6))

    # 个股因子 (20)
    stock_return_1d = Column(DECIMAL(12, 6))
    stock_return_5d = Column(DECIMAL(12, 6))
    stock_return_20d = Column(DECIMAL(12, 6))
    stock_volatility_20d = Column(DECIMAL(12, 6))
    stock_volatility_60d = Column(DECIMAL(12, 6))
    stock_volume_ratio_5d = Column(DECIMAL(12, 6))
    stock_turnover_rate_5d = Column(DECIMAL(12, 6))
    stock_pe_ttm = Column(DECIMAL(12, 6))
    stock_pb = Column(DECIMAL(12, 6))
    stock_ps_ttm = Column(DECIMAL(12, 6))
    stock_roe_ttm = Column(DECIMAL(12, 6))
    stock_roa_ttm = Column(DECIMAL(12, 6))
    stock_revenue_yoy = Column(DECIMAL(12, 6))
    stock_profit_yoy = Column(DECIMAL(12, 6))
    stock_gross_margin = Column(DECIMAL(12, 6))
    stock_debt_ratio = Column(DECIMAL(12, 6))
    stock_momentum_20d = Column(DECIMAL(12, 6))
    stock_reversal_5d = Column(DECIMAL(12, 6))
    stock_size_factor = Column(DECIMAL(12, 6))
    stock_illiquidity = Column(DECIMAL(12, 6))

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")