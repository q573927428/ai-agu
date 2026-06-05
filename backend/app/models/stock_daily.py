"""股票每日行情数据表 — 基于Tushare Pro daily接口"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class StockDaily(Base):
    __tablename__ = "stock_daily"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_code_date"),
        Index("idx_date", "trade_date"),
        Index("idx_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, comment="交易日期")

    # ── Tushare daily 接口字段 ──
    open = Column(DECIMAL(12, 3), comment="开盘价")
    high = Column(DECIMAL(12, 3), comment="最高价")
    low = Column(DECIMAL(12, 3), comment="最低价")
    close = Column(DECIMAL(12, 3), comment="收盘价")
    pre_close = Column(DECIMAL(12, 3), comment="昨收价(除权价)")
    change = Column(DECIMAL(12, 3), comment="涨跌额")
    pct_chg = Column(DECIMAL(12, 6), comment="涨跌幅(%)")

    # 单位换算：vol 手 → 股(×100)，amount 千元 → 元(×1000)
    volume = Column(BigInteger, comment="成交量(股)")
    amount = Column(DECIMAL(16, 2), comment="成交额(元)")