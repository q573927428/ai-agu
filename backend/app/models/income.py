"""利润表模型 — 对应 Tushare Pro income 接口"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, Integer, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class Income(Base):
    """利润表"""
    __tablename__ = "income"
    __table_args__ = (
        UniqueConstraint("stock_code", "end_date", "report_type", name="uk_stock_end_type"),
        Index("idx_end_date", "end_date"),
        Index("idx_stock_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期")
    report_type = Column(Integer, nullable=False, comment="报告类型 1=合并季报 2=合并年报 3=母公司季报 4=母公司年报")

    # ── 营收 ──
    revenue = Column(DECIMAL(20, 2), comment="营业总收入")
    revenue_yoy = Column(DECIMAL(10, 4), comment="营业总收入同比增长率(%)")
    cost = Column(DECIMAL(20, 2), comment="营业总成本")
    sell_expense = Column(DECIMAL(20, 2), comment="销售费用")
    admin_expense = Column(DECIMAL(20, 2), comment="管理费用")
    fin_expense = Column(DECIMAL(20, 2), comment="财务费用")
    rd_expense = Column(DECIMAL(20, 2), comment="研发费用")

    # ── 利润 ──
    operating_profit = Column(DECIMAL(20, 2), comment="营业利润")
    total_profit = Column(DECIMAL(20, 2), comment="利润总额")
    total_profit_yoy = Column(DECIMAL(10, 4), comment="利润总额同比增长率(%)")
    net_profit = Column(DECIMAL(20, 2), comment="归母净利润")
    net_profit_yoy = Column(DECIMAL(10, 4), comment="净利润同比增长率(%)")
    non_op_income = Column(DECIMAL(20, 2), comment="营业外收入")
    non_op_expense = Column(DECIMAL(20, 2), comment="营业外支出")
    income_tax = Column(DECIMAL(20, 2), comment="所得税费用")
    minority_pl = Column(DECIMAL(20, 2), comment="少数股东损益")

    # ── 每股 ──
    eps = Column(DECIMAL(10, 4), comment="基本每股收益")
    diluted_eps = Column(DECIMAL(10, 4), comment="稀释每股收益")
    eps_yoy = Column(DECIMAL(10, 4), comment="每股收益同比增长率(%)")

    # ── 系统字段 ──
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")