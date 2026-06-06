"""现金流量表模型 — 对应 Tushare Pro cashflow 接口"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, Integer, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class Cashflow(Base):
    """现金流量表"""
    __tablename__ = "cashflow"
    __table_args__ = (
        UniqueConstraint("stock_code", "end_date", "report_type", name="uk_stock_end_type"),
        Index("idx_end_date", "end_date"),
        Index("idx_stock_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期")
    report_type = Column(Integer, nullable=False, comment="报告类型 1=合并季报 2=合并年报 3=母公司季报 4=母公司年报")

    # ── 经营活动 ──
    oper_cash_in = Column(DECIMAL(20, 2), comment="经营活动现金流入")
    oper_cash_out = Column(DECIMAL(20, 2), comment="经营活动现金流出")
    net_oper_cash = Column(DECIMAL(20, 2), comment="经营活动现金流量净额")

    # ── 投资活动 ──
    inv_cash_in = Column(DECIMAL(20, 2), comment="投资活动现金流入")
    inv_cash_out = Column(DECIMAL(20, 2), comment="投资活动现金流出")
    net_inv_cash = Column(DECIMAL(20, 2), comment="投资活动现金流量净额")

    # ── 筹资活动 ──
    fin_cash_in = Column(DECIMAL(20, 2), comment="筹资活动现金流入")
    fin_cash_out = Column(DECIMAL(20, 2), comment="筹资活动现金流出")
    net_fin_cash = Column(DECIMAL(20, 2), comment="筹资活动现金流量净额")

    # ── 汇总 ──
    cash_equiv_net = Column(DECIMAL(20, 2), comment="现金等价物净增加额")
    free_cashflow = Column(DECIMAL(20, 2), comment="自由现金流")

    # ── 系统字段 ──
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")