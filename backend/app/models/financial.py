"""财务数据表"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, UniqueConstraint, Index
from .base import Base


class Financial(Base):
    __tablename__ = "financial"
    __table_args__ = (
        UniqueConstraint("stock_code", "report_date", name="uk_code_report"),
        Index("idx_report_date", "report_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    report_date = Column(Date, nullable=False, comment="报告期")
    report_type = Column(String(10), comment="报告类型(Q1/Q2/Q3/Q4/FY)")
    revenue = Column(DECIMAL(20, 2), comment="营业收入")
    revenue_yoy = Column(DECIMAL(10, 4), comment="营收同比增长率(%)")
    net_profit = Column(DECIMAL(20, 2), comment="归母净利润")
    net_profit_yoy = Column(DECIMAL(10, 4), comment="净利润同比增长率(%)")
    gross_margin = Column(DECIMAL(10, 4), comment="毛利率(%)")
    net_margin = Column(DECIMAL(10, 4), comment="净利率(%)")
    roe = Column(DECIMAL(10, 4), comment="净资产收益率(%)")
    roa = Column(DECIMAL(10, 4), comment="总资产收益率(%)")
    debt_ratio = Column(DECIMAL(10, 4), comment="资产负债率(%)")
    current_ratio = Column(DECIMAL(10, 4), comment="流动比率")
    quick_ratio = Column(DECIMAL(10, 4), comment="速动比率")
    total_assets = Column(DECIMAL(20, 2), comment="总资产")
    total_equity = Column(DECIMAL(20, 2), comment="净资产")
    operating_cashflow = Column(DECIMAL(20, 2), comment="经营活动现金流净额")
    free_cashflow = Column(DECIMAL(20, 2), comment="自由现金流")