"""股票基础信息表 — 基于Tushare Pro stock_basic接口完整字段"""
from sqlalchemy import Column, String, Enum, Date, Integer, DateTime
from sqlalchemy.sql import func
from .base import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    # ── 关键标识（向后兼容） ──
    stock_code = Column(String(10), primary_key=True, comment="股票代码(纯数字)")
    ts_code = Column(String(12), comment="TS代码(带后缀 如 000001.SZ)")

    # ── 基础信息 ──
    stock_name = Column(String(50), nullable=False, comment="股票名称")
    area = Column(String(20), comment="地域")
    industry = Column(String(50), comment="所属行业")
    fullname = Column(String(100), comment="股票全称")
    enname = Column(String(100), comment="英文全称")
    cnspell = Column(String(10), comment="拼音缩写")
    market = Column(String(20), comment="市场类型（主板/创业板/科创板/CDR）")
    exchange = Column(String(10), comment="交易所代码 SSE/SZSE/BSE")
    curr_type = Column(String(10), comment="交易货币")

    # ── 上市状态 ──
    list_status = Column(String(1), default="L", comment="上市状态 L上市 D退市")
    list_date = Column(Date, comment="上市日期")
    delist_date = Column(Date, comment="退市日期")
    is_hs = Column(String(1), comment="是否沪深港通标的 N否 H沪股通 S深股通")

    # ── 实控人 ──
    act_name = Column(String(100), comment="实控人名称")
    act_ent_type = Column(String(50), comment="实控人企业性质")

    # ── 系统字段 ──
    is_active = Column(Integer, default=1, comment="是否活跃")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")