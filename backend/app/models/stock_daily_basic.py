"""每日基本面指标表 — 基于Tushare Pro daily_basic接口"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class StockDailyBasic(Base):
    """每日基本面指标

    对应 Tushare Pro daily_basic 接口，按日线提取全量历史数据。
    (stock_code, trade_date) 唯一键，支持 upsert。

    该表存储完整历史，最新值通过流水线同步到 stock_basic 快照字段。
    """
    __tablename__ = "stock_daily_basic"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_code_date"),
        Index("idx_date", "trade_date"),
        Index("idx_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码(纯数字)")
    trade_date = Column(Date, nullable=False, comment="交易日期")

    # ── Tushare daily_basic 接口字段 ──
    close = Column(DECIMAL(12, 3), comment="当日收盘价")
    turnover_rate = Column(DECIMAL(12, 6), comment="换手率(%)")
    turnover_rate_f = Column(DECIMAL(12, 6), comment="换手率(自由流通股%)")
    volume_ratio = Column(DECIMAL(12, 6), comment="量比")
    pe = Column(DECIMAL(12, 6), comment="市盈率(总市值/净利润)")
    pe_ttm = Column(DECIMAL(12, 6), comment="市盈率(TTM)")
    pb = Column(DECIMAL(12, 6), comment="市净率(总市值/净资产)")
    ps = Column(DECIMAL(12, 6), comment="市销率")
    ps_ttm = Column(DECIMAL(12, 6), comment="市销率(TTM)")
    dv_ratio = Column(DECIMAL(12, 6), comment="股息率(%)")
    dv_ttm = Column(DECIMAL(12, 6), comment="股息率(TTM)(%)")
    total_share = Column(DECIMAL(16, 2), comment="总股本(万股)")
    float_share = Column(DECIMAL(16, 2), comment="流通股本(万股)")
    free_share = Column(DECIMAL(16, 2), comment="自由流通股本(万股)")
    total_mv = Column(DECIMAL(16, 2), comment="总市值(万元)")
    circ_mv = Column(DECIMAL(16, 2), comment="流通市值(万元)")

    # ── 系统字段 ──
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")