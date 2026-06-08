"""因子存储表（宽表设计）"""
from sqlalchemy import Column, String, Date, BigInteger, DECIMAL, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class FactorStore(Base):
    """因子存储表 - 存储计算好的各类量化因子数据，包含宏观、市场、行业、个股四类因子"""
    __tablename__ = "factor_store"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uk_code_date"),
        Index("idx_date", "trade_date"),
        Index("idx_stock_date", "stock_code", "trade_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, comment="交易日")

    # 宏观因子 (15) - 反映宏观经济环境，更新频率较低（月/季度）
    macro_gdp_yoy = Column(DECIMAL(12, 6), comment="GDP同比增速")
    macro_cpi_yoy = Column(DECIMAL(12, 6), comment="CPI同比增速")
    macro_ppi_yoy = Column(DECIMAL(12, 6), comment="PPI同比增速")
    macro_pmi = Column(DECIMAL(12, 6), comment="制造业采购经理指数(PMI)")
    macro_m2_yoy = Column(DECIMAL(12, 6), comment="M2货币供应量同比增速")
    macro_shibor_on = Column(DECIMAL(12, 6), comment="Shibor隔夜利率")
    macro_shibor_1m = Column(DECIMAL(12, 6), comment="Shibor1个月利率")
    macro_usdcny = Column(DECIMAL(12, 6), comment="美元兑人民币汇率")
    macro_hgt = Column(DECIMAL(12, 6), comment="沪股通资金净流入(亿元)")
    macro_sgt = Column(DECIMAL(12, 6), comment="深股通资金净流入(亿元)")
    macro_north_flow = Column(DECIMAL(12, 6), comment="北向资金合计净流入(亿元)")
    macro_margin_balance = Column(DECIMAL(12, 6), comment="融资融券余额(亿元)")
    macro_us_y3m = Column(DECIMAL(12, 6), comment="美国3个月国债收益率(%)")
    macro_us_y2y = Column(DECIMAL(12, 6), comment="美国2年期国债收益率(%)")
    macro_us_y10y = Column(DECIMAL(12, 6), comment="美国10年期国债收益率(%)")

    # 市场因子 (10) - 反映整体市场状况
    market_idx_return_5d = Column(DECIMAL(12, 6), comment="市场指数5日收益率")
    market_idx_return_20d = Column(DECIMAL(12, 6), comment="市场指数20日收益率")
    market_idx_volatility_20d = Column(DECIMAL(12, 6), comment="市场指数20日年化波动率")
    market_turnover_ma5 = Column(DECIMAL(12, 6), comment="市场5日平均换手率")
    market_advance_decline_ratio = Column(DECIMAL(12, 6), comment="市场涨跌比(上涨家数/下跌家数)")
    market_volume_ratio = Column(DECIMAL(12, 6), comment="市场量比(当日成交量/5日均量)")
    market_breadth_20d = Column(DECIMAL(12, 6), comment="市场20日宽度指标(创新高-创新低占比)")
    market_vix_proxy = Column(DECIMAL(12, 6), comment="市场恐慌指数代理(隐含波动率)")
    market_style_momentum = Column(DECIMAL(12, 6), comment="市场风格动量因子")
    market_style_value = Column(DECIMAL(12, 6), comment="市场风格价值因子")

    # 行业因子 (10) - 反映个股所属行业特征
    industry_return_5d = Column(DECIMAL(12, 6), comment="行业5日收益率")
    industry_return_20d = Column(DECIMAL(12, 6), comment="行业20日收益率")
    industry_return_volatility = Column(DECIMAL(12, 6), comment="行业收益波动率")
    industry_pe_percentile = Column(DECIMAL(12, 6), comment="行业PE历史百分位")
    industry_pb_percentile = Column(DECIMAL(12, 6), comment="行业PB历史百分位")
    industry_roe_median = Column(DECIMAL(12, 6), comment="行业ROE中位数")
    industry_momentum_rank = Column(DECIMAL(12, 6), comment="行业动量排名(涨幅相对排名)")
    industry_reversal_signal = Column(DECIMAL(12, 6), comment="行业反转信号")
    industry_fund_flow = Column(DECIMAL(12, 6), comment="行业资金净流入(亿元)")
    industry_dispersion = Column(DECIMAL(12, 6), comment="行业离散度(行业内个股收益标准差)")

    # 个股因子 (20) - 反映个股自身特征
    stock_return_1d = Column(DECIMAL(12, 6), comment="个股1日收益率")
    stock_return_5d = Column(DECIMAL(12, 6), comment="个股5日收益率")
    stock_return_20d = Column(DECIMAL(12, 6), comment="个股20日收益率")
    stock_volatility_20d = Column(DECIMAL(12, 6), comment="个股20日年化波动率")
    stock_volatility_60d = Column(DECIMAL(12, 6), comment="个股60日年化波动率")
    stock_volume_ratio_5d = Column(DECIMAL(12, 6), comment="个股5日量比(均量/20日均量)")
    stock_turnover_rate_5d = Column(DECIMAL(12, 6), comment="个股5日平均换手率(%)")
    stock_pe_ttm = Column(DECIMAL(12, 6), comment="个股滚动市盈率(PE-TTM)")
    stock_pb = Column(DECIMAL(12, 6), comment="个股市净率(PB)")
    stock_ps_ttm = Column(DECIMAL(12, 6), comment="个股滚动市销率(PS-TTM)")
    stock_roe_ttm = Column(DECIMAL(12, 6), comment="个股滚动净资产收益率(ROE-TTM,%)")
    stock_roa_ttm = Column(DECIMAL(12, 6), comment="个股滚动总资产收益率(ROA-TTM,%)")
    stock_revenue_yoy = Column(DECIMAL(12, 6), comment="个股营业收入同比增速(%)")
    stock_profit_yoy = Column(DECIMAL(12, 6), comment="个股净利润同比增速(%)")
    stock_gross_margin = Column(DECIMAL(12, 6), comment="个股毛利率(%)")
    stock_debt_ratio = Column(DECIMAL(12, 6), comment="个股资产负债率(%)")
    stock_momentum_20d = Column(DECIMAL(12, 6), comment="个股20日动量因子(剔除最近1日收益率)")
    stock_reversal_5d = Column(DECIMAL(12, 6), comment="个股5日反转因子(负的5日收益率)")
    stock_size_factor = Column(DECIMAL(12, 6), comment="个股规模因子(对数总市值)")
    stock_illiquidity = Column(DECIMAL(12, 6), comment="个股非流动性指标(Amihud,收益率/成交额)")

    # 元数据
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
