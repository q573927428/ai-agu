"""股票基础信息表"""
from sqlalchemy import Column, String, Enum, Date, Integer, DateTime, text
from sqlalchemy.sql import func
from .base import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    stock_code = Column(String(10), primary_key=True, comment="股票代码")
    stock_name = Column(String(50), nullable=False, comment="股票名称")
    industry = Column(String(50), comment="申万一级行业")
    sub_industry = Column(String(50), comment="申万二级行业")
    area = Column(String(20), comment="所属地区")
    market = Column(Enum("SH", "SZ", "BJ"), comment="交易所")
    list_date = Column(Date, comment="上市日期")
    is_active = Column(Integer, default=1, comment="是否活跃")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")