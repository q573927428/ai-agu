"""AkShare数据采集服务"""
import pandas as pd
from typing import Optional
from datetime import datetime
from loguru import logger


class DataFetcher:
    """AkShare数据采集服务"""

    async def fetch_all_stock_basic(self) -> pd.DataFrame:
        """获取全市场A股基础信息"""
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            logger.info(f"获取股票基础信息: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            return pd.DataFrame()

    async def fetch_stock_daily_batch(self, date: str) -> pd.DataFrame:
        """获取指定日期全市场股票日数据"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                df["trade_date"] = date
                logger.info(f"获取 {date} 行情数据: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            return pd.DataFrame()

    async def fetch_financial_data(self, stock_code: str) -> dict:
        """获取财务数据"""
        try:
            import akshare as ak
            df = ak.stock_financial_abstract(symbol=stock_code)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict() if len(df) > 0 else {}
            return {}
        except Exception as e:
            logger.error(f"获取 {stock_code} 财务数据失败: {e}")
            return {}

    async def fetch_macro_data(self) -> dict:
        """获取宏观经济数据"""
        try:
            import akshare as ak
            data = {}

            # GDP
            gdp_df = ak.macro_china_gdp_yearly()
            if gdp_df is not None and not gdp_df.empty:
                data["gdp_yoy"] = float(gdp_df.iloc[-1]["同比"])

            # CPI
            cpi_df = ak.macro_china_cpi_yearly()
            if cpi_df is not None and not cpi_df.empty:
                data["cpi_yoy"] = float(cpi_df.iloc[-1]["同比"])

            # PMI
            pmi_df = ak.macro_china_pmi()
            if pmi_df is not None and not pmi_df.empty:
                data["pmi"] = float(pmi_df.iloc[-1]["现值"])

            # M2
            m2_df = ak.macro_china_money_supply()
            if m2_df is not None and not m2_df.empty:
                data["m2_yoy"] = float(m2_df.iloc[-1]["同比增长"])

            logger.info(f"获取宏观经济数据成功")
            return data
        except Exception as e:
            logger.error(f"获取宏观经济数据失败: {e}")
            return {}

    async def fetch_market_index(self) -> pd.DataFrame:
        """获取市场指数数据"""
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol="sh000001")
            logger.info(f"获取上证指数数据: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return pd.DataFrame()

    async def fetch_north_flow(self) -> pd.DataFrame:
        """获取北向资金数据"""
        try:
            import akshare as ak
            df = ak.stock_hsgt_north_net_flow_in_em()
            return df
        except Exception as e:
            logger.error(f"获取北向资金数据失败: {e}")
            return pd.DataFrame()