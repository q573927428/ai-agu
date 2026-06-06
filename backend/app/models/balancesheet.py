"""资产负债表模型 — 对应 Tushare Pro balancesheet 接口"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, Integer, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class Balancesheet(Base):
    """资产负债表"""
    __tablename__ = "balancesheet"
    __table_args__ = (
        UniqueConstraint("stock_code", "end_date", "report_type", name="uk_stock_end_type"),
        Index("idx_end_date", "end_date"),
        Index("idx_stock_code", "stock_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期")
    report_type = Column(Integer, nullable=False, comment="报告类型 1=合并季报 2=合并年报 3=母公司季报 4=母公司年报")

    # ── 资产 ──
    total_assets = Column(DECIMAL(20, 2), comment="总资产")
    current_assets = Column(DECIMAL(20, 2), comment="流动资产")
    money_cap = Column(DECIMAL(20, 2), comment="货币资金")
    accounts_rece = Column(DECIMAL(20, 2), comment="应收账款")
    inventory = Column(DECIMAL(20, 2), comment="存货")
    fixed_assets = Column(DECIMAL(20, 2), comment="固定资产")
    intan_assets = Column(DECIMAL(20, 2), comment="无形资产")
    goodwill = Column(DECIMAL(20, 2), comment="商誉")

    # ── 负债 ──
    total_liab = Column(DECIMAL(20, 2), comment="总负债")
    current_liab = Column(DECIMAL(20, 2), comment="流动负债")
    accounts_pay = Column(DECIMAL(20, 2), comment="应付账款")
    longterm_loan = Column(DECIMAL(20, 2), comment="长期借款")
    bonds_payable = Column(DECIMAL(20, 2), comment="应付债券")

    # ── 权益 ──
    total_equity = Column(DECIMAL(20, 2), comment="净资产(归属母公司)")
    minority_int = Column(DECIMAL(20, 2), comment="少数股东权益")
    cap_stk = Column(DECIMAL(20, 2), comment="实收资本(股本)")
    cap_reserve = Column(DECIMAL(20, 2), comment="资本公积金")
    surplus_reserve = Column(DECIMAL(20, 2), comment="盈余公积金")
    retained_earn = Column(DECIMAL(20, 2), comment="未分配利润")

    # ── 系统字段 ──
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")