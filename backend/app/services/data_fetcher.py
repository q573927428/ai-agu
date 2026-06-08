"""Tushare 数据采集服务"""
import pandas as pd
from typing import Optional
from datetime import datetime
from loguru import logger
from app.config import settings


class DataFetcher:
    """Tushare 数据采集服务"""

    def _get_pro(self):
        """获取 Tushare Pro API 实例"""
        import tushare as ts
        token = settings.tushare_token or "0c5fcf150b255ac8295383e5f0ba8fc96c0ab39fcd3e7718aa3a8f0b"
        ts.set_token(token)
        return ts.pro_api()

    async def fetch_all_stock_basic(self) -> pd.DataFrame:
        """获取全市场A股基础信息"""
        try:
            pro = self._get_pro()
            df = pro.stock_basic(exchange='', list_status='L',
                                 fields='ts_code,symbol,name,area,industry,list_date')
            logger.info(f"获取股票基础信息: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            return pd.DataFrame()

    async def fetch_stock_daily_batch(self, date: str) -> pd.DataFrame:
        """获取指定日期全市场股票日数据"""
        try:
            pro = self._get_pro()
            df = pro.daily(trade_date=date.replace("-", ""))
            if df is not None and not df.empty:
                logger.info(f"获取 {date} 行情数据: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            return pd.DataFrame()

    async def fetch_financial_data(self, stock_code: str) -> dict:
        """获取财务数据"""
        try:
            pro = self._get_pro()
            # 取最近一期财务数据
            df = pro.fina_indicator(ts_code=stock_code, limit=1)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
            return {}
        except Exception as e:
            logger.error(f"获取 {stock_code} 财务数据失败: {e}")
            return {}

    async def fetch_macro_data(self) -> dict:
        """获取宏观经济数据"""
        try:
            pro = self._get_pro()
            data = {}

            # GDP
            gdp_df = pro.cn_gdp()
            if gdp_df is not None and not gdp_df.empty:
                data["gdp_yoy"] = float(gdp_df.iloc[-1]["gdp_yoy"])

            # CPI
            cpi_df = pro.cn_cpi()
            if cpi_df is not None and not cpi_df.empty:
                data["cpi_yoy"] = float(cpi_df.iloc[-1]["cpi_yoy"])

            # PMI
            pmi_df = pro.cn_pmi()
            if pmi_df is not None and not pmi_df.empty:
                data["pmi"] = float(pmi_df.iloc[-1]["pmi"])

            # M2
            m2_df = pro.cn_m2()
            if m2_df is not None and not m2_df.empty:
                data["m2_yoy"] = float(m2_df.iloc[-1]["m2_yoy"])

            logger.info("获取宏观经济数据成功")
            return data
        except Exception as e:
            logger.error(f"获取宏观经济数据失败: {e}")
            return {}

    async def fetch_market_index(self) -> pd.DataFrame:
        """获取上证指数历史日线"""
        try:
            pro = self._get_pro()
            df = pro.index_daily(ts_code="000001.SH")
            logger.info(f"获取上证指数数据: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return pd.DataFrame()

    async def fetch_north_flow(self) -> pd.DataFrame:
        """获取北向资金数据"""
        try:
            pro = self._get_pro()
            df = pro.moneyflow_hsgt()
            return df
        except Exception as e:
            logger.error(f"获取北向资金数据失败: {e}")
            return pd.DataFrame()