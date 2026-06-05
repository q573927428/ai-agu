"""宏观经济数据表"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, UniqueConstraint, Index
from .base import Base


class MacroData(Base):
    __tablename__ = "macro_data"
    __table_args__ = (
        UniqueConstraint("data_date", name="uk_date"),
        Index("idx_date", "data_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False, comment="数据日期")
    gdp_yoy = Column(DECIMAL(10, 4), comment="GDP同比(%)")
    gdp_qoq = Column(DECIMAL(10, 4), comment="GDP环比(%)")
    cpi_yoy = Column(DECIMAL(10, 4), comment="CPI同比(%)")
    ppi_yoy = Column(DECIMAL(10, 4), comment="PPI同比(%)")
    pmi = Column(DECIMAL(10, 4), comment="制造业PMI")
    pmi_service = Column(DECIMAL(10, 4), comment="服务业PMI")
    m2_yoy = Column(DECIMAL(10, 4), comment="M2同比(%)")
    m1_yoy = Column(DECIMAL(10, 4), comment="M1同比(%)")
    social_finance = Column(DECIMAL(20, 2), comment="社会融资规模(亿元)")
    shibor_1m = Column(DECIMAL(10, 4), comment="SHIBOR 1个月(%)")
    bond_10y_yield = Column(DECIMAL(10, 4), comment="10年期国债收益率(%)")
    credit_spread = Column(DECIMAL(10, 4), comment="信用利差(%)")
    usdcny = Column(DECIMAL(10, 4), comment="美元兑人民币汇率")
    market_sentiment = Column(DECIMAL(10, 4), comment="市场情绪指数")
    margin_balance = Column(DECIMAL(20, 2), comment="融资余额(亿元)")
    north_flow = Column(DECIMAL(20, 2), comment="北向资金净流入(亿元)")