"""宏观经济数据表 — 基于Tushare Pro重新设计"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, UniqueConstraint, Index
from .base import Base


class MacroData(Base):
    """宏观经济数据

    数据来源：Tushare Pro
    - 月度/季度数据本月不更新时取最近一期
    - 日频数据取当天
    """
    __tablename__ = "macro_data"
    __table_args__ = (
        UniqueConstraint("data_date", name="uk_date"),
        Index("idx_date", "data_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    data_date = Column(Date, nullable=False, comment="数据日期")

    # ── 国民经济核算 (cn_gdp, 季度) ──
    gdp_yoy = Column(DECIMAL(10, 4), comment="GDP同比(%)")
    gdp = Column(DECIMAL(20, 2), comment="GDP绝对值(亿元)")

    # ── 价格指数 (月度) ──
    cpi_yoy = Column(DECIMAL(10, 4), comment="CPI同比(%)")         # cn_cpi -> nt_yoy
    cpi_val = Column(DECIMAL(10, 4), comment="CPI绝对值")           # cn_cpi -> nt_val
    ppi_yoy = Column(DECIMAL(10, 4), comment="PPI同比(%)")          # cn_ppi -> ppi_yoy

    # ── 采购经理指数 (cn_pmi, 月度) ──
    pmi = Column(DECIMAL(10, 4), comment="制造业PMI(%)")
    pmi_service = Column(DECIMAL(10, 4), comment="非制造业PMI(%)")

    # ── 货币供应量 (月度) ──
    m2_yoy = Column(DECIMAL(10, 4), comment="M2同比(%)")

    # ── 利率 / 货币市场 (日频) ──
    shibor_on = Column(DECIMAL(10, 4), comment="SHIBOR隔夜(%)")    # shibor -> on
    shibor_1w = Column(DECIMAL(10, 4), comment="SHIBOR 1周(%)")    # shibor -> 1w
    shibor_1m = Column(DECIMAL(10, 4), comment="SHIBOR 1个月(%)")  # shibor -> 1m
    shibor_1y = Column(DECIMAL(10, 4), comment="SHIBOR 1年(%)")    # shibor -> 1y

    # ── 汇率 (日频) ──
    usdcny = Column(DECIMAL(10, 6), comment="美元兑人民币(在岸)")

    # ── 沪深港通资金 (moneyflow_hsgt, 日频) ──
    hgt = Column(DECIMAL(20, 2), comment="沪股通资金(亿元)")        # moneyflow_hsgt -> hgt
    sgt = Column(DECIMAL(20, 2), comment="深股通资金(亿元)")        # moneyflow_hsgt -> sgt
    north_flow = Column(DECIMAL(20, 2), comment="北向资金合计(亿元)")  # moneyflow_hsgt -> north_money

    # ── 融资融券 (margin, 日频) ──
    margin_balance = Column(DECIMAL(20, 2), comment="融资余额(万元)")

    # ── 美国国债收益率曲线 (us_tycr, 日频) ──
    us_y3m = Column(DECIMAL(10, 4), comment="美国3个月国债收益率(%)")   # m3
    us_y2y = Column(DECIMAL(10, 4), comment="美国2年期国债收益率(%)")    # y2
    us_y10y = Column(DECIMAL(10, 4), comment="美国10年期国债收益率(%)")  # y10
