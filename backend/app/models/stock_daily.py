"""股票每日行情数据表"""
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
    open = Column(DECIMAL(12, 3), comment="开盘价")
    high = Column(DECIMAL(12, 3), comment="最高价")
    low = Column(DECIMAL(12, 3), comment="最低价")
    close = Column(DECIMAL(12, 3), comment="收盘价")
    pre_close = Column(DECIMAL(12, 3), comment="前收盘价")
    volume = Column(BigInteger, comment="成交量(股)")
    amount = Column(DECIMAL(16, 2), comment="成交额(元)")
    turnover_rate = Column(DECIMAL(10, 4), comment="换手率(%)")
    pe = Column(DECIMAL(12, 4), comment="市盈率")
    pe_ttm = Column(DECIMAL(12, 4), comment="市盈率TTM")
    pb = Column(DECIMAL(12, 4), comment="市净率")
    ps = Column(DECIMAL(12, 4), comment="市销率")
    pcf = Column(DECIMAL(12, 4), comment="市现率")
    total_mv = Column(DECIMAL(16, 2), comment="总市值(元)")
    float_mv = Column(DECIMAL(16, 2), comment="流通市值(元)")