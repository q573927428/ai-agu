"""指数日线行情数据表"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, UniqueConstraint, Index
from .base import Base


class IndexDaily(Base):
    """指数每日行情
    数据来源：Tushare Pro index_daily
    """
    __tablename__ = "index_daily"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uk_index_date"),
        Index("idx_index_date", "trade_date"),
        Index("idx_ts_code", "ts_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(12), nullable=False, comment="TS代码(如 000001.SH)")
    trade_date = Column(Date, nullable=False, comment="交易日期")

    # ── Tushare index_daily 接口字段 ──
    open = Column(DECIMAL(12, 3), comment="开盘价")
    high = Column(DECIMAL(12, 3), comment="最高价")
    low = Column(DECIMAL(12, 3), comment="最低价")
    close = Column(DECIMAL(12, 3), comment="收盘价")
    pre_close = Column(DECIMAL(12, 3), comment="昨收价")
    change = Column(DECIMAL(12, 3), comment="涨跌点")
    pct_chg = Column(DECIMAL(12, 6), comment="涨跌幅(%)")
    vol = Column(DECIMAL(20, 2), comment="成交量(手)")
    amount = Column(DECIMAL(20, 2), comment="成交额(万元)")