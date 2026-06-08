"""股票事件表 — 拆股、分红送股等导致除权除息的事件"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, DateTime, Index, text
from sqlalchemy.sql import func
from .base import Base


class StockEvent(Base):
    __tablename__ = "stock_event"
    __table_args__ = (
        Index("idx_stock_date", "stock_code", "ex_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    ex_date = Column(Date, nullable=False, comment="除权除息日")
    event_type = Column(String(20), nullable=False, comment="事件类型: split_bonus(送转) / cash_dividend(现金分红) / mixed(混合)")
    description = Column(String(100), comment="描述文字，如 10送5转3派1.2")

    # dividend 接口原始字段
    end_date = Column(String(10), comment="分红年度")
    ann_date = Column(Date, comment="预案公告日")
    div_proc = Column(String(10), comment="实施进度")
    stk_div = Column(DECIMAL(12, 6), comment="每股送转合计")
    stk_bo_rate = Column(DECIMAL(12, 6), comment="每股送股比例")
    stk_co_rate = Column(DECIMAL(12, 6), comment="每股转增比例")
    cash_div = Column(DECIMAL(12, 6), comment="每股分红（税后）")
    cash_div_tax = Column(DECIMAL(12, 6), comment="每股分红（税前）")
    record_date = Column(Date, comment="股权登记日")
    pay_date = Column(Date, comment="派息日")
    div_listdate = Column(Date, comment="红股上市日")
    imp_ann_date = Column(Date, comment="实施公告日")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        return {
            "ex_date": str(self.ex_date) if self.ex_date else None,
            "event_type": self.event_type,
            "description": self.description,
            "stk_div": float(self.stk_div) if self.stk_div else 0,
            "stk_bo_rate": float(self.stk_bo_rate) if self.stk_bo_rate else 0,
            "stk_co_rate": float(self.stk_co_rate) if self.stk_co_rate else 0,
            "cash_div": float(self.cash_div) if self.cash_div else 0,
        }