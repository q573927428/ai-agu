"""因子计算引擎"""
import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from app.models.factor import FactorStore
from app.models.stock_daily import StockDaily
from app.models.macro import MacroData


class FactorEngine:
    """因子计算引擎 - 计算全部50个因子"""

    def __init__(self, db: Session):
        self.db = db

    def preprocess_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """因子预处理：去极值(MAD)、标准化(Z-Score)"""
        if df is None or df.empty:
            return df

        df = df.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        # 缺失值填充（列中位数）
        for col in numeric_cols:
            df[col] = df[col].fillna(df[col].median())

        # MAD法去极值（5倍中位数绝对偏差）
        for col in numeric_cols:
            median = df[col].median()
            mad = np.median(np.abs(df[col] - median))
            if mad > 0:
                upper = median + 5 * mad
                lower = median - 5 * mad
                df[col] = df[col].clip(lower, upper)

        # Z-Score标准化
        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                df[col] = (df[col] - mean) / std

        return df

    def compute_macro_factors(self, trade_date: str) -> pd.Series:
        """计算宏观因子"""
        macro = self.db.query(MacroData).order_by(MacroData.data_date.desc()).first()
        if not macro:
            return pd.Series(dtype=float)

        return pd.Series({
            "macro_gdp_yoy": float(macro.gdp_yoy or 0),
            "macro_cpi_yoy": float(macro.cpi_yoy or 0),
            "macro_ppi_yoy": float(macro.ppi_yoy or 0),
            "macro_pmi": float(macro.pmi or 0),
            "macro_m2_yoy": float(macro.m2_yoy or 0),
            "macro_shibor_on": float(macro.shibor_on or 0),
            "macro_shibor_1m": float(macro.shibor_1m or 0),
            "macro_hgt": float(macro.hgt or 0),
            "macro_sgt": float(macro.sgt or 0),
            "macro_north_flow": float(macro.north_flow or 0),
            "macro_margin_balance": float(macro.margin_balance or 0),
            "macro_us_y3m": float(macro.us_y3m or 0),
            "macro_us_y2y": float(macro.us_y2y or 0),
            "macro_us_y10y": float(macro.us_y10y or 0),
        })

    def compute_stock_factors(self, stock_code: str, trade_date: str) -> dict:
        """计算个股因子"""
        from app.utils.date_utils import get_previous_n_trade_days

        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        past_dates = get_previous_n_trade_days(trade_date_dt, 60)

        # 获取历史行情
        daily_records = (
            self.db.query(StockDaily)
            .filter(
                StockDaily.stock_code == stock_code,
                StockDaily.trade_date.in_([d.date() for d in past_dates]),
            )
            .order_by(StockDaily.trade_date.asc())
            .all()
        )

        if len(daily_records) < 5:
            return {}

        closes = [float(r.close) for r in daily_records if r.close]
        volumes = [float(r.volume) for r in daily_records if r.volume]
        amounts = [float(r.amount) for r in daily_records if r.amount]
        turnovers = [float(r.pct_chg or 0) for r in daily_records if r.pct_chg is not None]

        if len(closes) < 5:
            return {}

        closes_arr = np.array(closes)
        returns = np.diff(closes_arr) / closes_arr[:-1]

        factors = {}

        # S01-S03: 收益率因子
        factors["stock_return_1d"] = float(returns[-1]) if len(returns) >= 1 else 0
        factors["stock_return_5d"] = float(closes_arr[-1] / closes_arr[-min(6, len(closes_arr))] - 1) if len(closes_arr) >= 6 else 0
        factors["stock_return_20d"] = float(closes_arr[-1] / closes_arr[-min(21, len(closes_arr))] - 1) if len(closes_arr) >= 21 else 0

        # S04-S05: 波动率因子
        factors["stock_volatility_20d"] = float(np.std(returns[-20:]) * np.sqrt(252)) if len(returns) >= 20 else 0
        factors["stock_volatility_60d"] = float(np.std(returns) * np.sqrt(252)) if len(returns) >= 2 else 0

        # S06: 量比
        vol_5 = np.mean(volumes[-5:]) if len(volumes) >= 5 else 0
        vol_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else (vol_5 or 1)
        factors["stock_volume_ratio_5d"] = float(vol_5 / vol_20) if vol_20 > 0 else 1

        # S07: 换手率
        factors["stock_turnover_rate_5d"] = float(np.mean(turnovers[-5:])) if len(turnovers) >= 5 else 0

        # 最新一日的数据
        latest = daily_records[-1]

        # S08-S10: 估值因子（daily接口不含，暂为0）
        factors["stock_pe_ttm"] = 0
        factors["stock_pb"] = 0
        factors["stock_ps_ttm"] = 0

        # S17: 20日动量（剔除最近1日）
        factors["stock_momentum_20d"] = float(closes_arr[-2] / closes_arr[-min(21, len(closes_arr))] - 1) if len(closes_arr) >= 21 else 0

        # S18: 5日反转
        factors["stock_reversal_5d"] = -factors["stock_return_5d"]

        # S19: 规模因子（daily接口不含总市值，暂为0）
        factors["stock_size_factor"] = 0

        # S20: 非流动性
        if len(returns) >= 20 and len(amounts) >= 20:
            illiq = np.mean(np.abs(returns[-20:]) / (np.array(amounts[-20:]) / 1e8))
            factors["stock_illiquidity"] = float(illiq) if not np.isnan(illiq) and not np.isinf(illiq) else 0
        else:
            factors["stock_illiquidity"] = 0

        return factors

    def compute_all(self, trade_date: str, top_n: int = 0) -> pd.DataFrame:
        """计算全市场全部因子，输出因子宽表

        Args:
            trade_date: 交易日期
            top_n: 限制股票数量，0=全部
        """
        query = self.db.query(StockDaily.stock_code).filter(
            StockDaily.trade_date == trade_date
        ).distinct()
        
        if top_n > 0:
            query = query.limit(top_n)
        
        stocks = query.all()

        macro_factors = self.compute_macro_factors(trade_date)
        all_factors = []

        for (stock_code,) in stocks:
            stock_factors = self.compute_stock_factors(stock_code, trade_date)
            if not stock_factors:
                continue

            row = {
                "stock_code": stock_code,
                "trade_date": trade_date,
                **macro_factors.to_dict(),
                **stock_factors,
            }
            all_factors.append(row)

        if not all_factors:
            return pd.DataFrame()

        df = pd.DataFrame(all_factors)
        df = self.preprocess_factors(df)
        logger.info(f"因子计算完成: {len(df)} 只股票, {len(df.columns) - 2} 个因子")
        return df

    def save_factors(self, df: pd.DataFrame):
        """保存因子数据到factor_store表"""
        if df is None or df.empty:
            return

        records = df.to_dict("records")
        for record in records:
            stock_code = record.pop("stock_code")
            trade_date = record.pop("trade_date")

            # 检查是否已存在
            existing = self.db.query(FactorStore).filter(
                FactorStore.stock_code == stock_code,
                FactorStore.trade_date == trade_date,
            ).first()

            if existing:
                for key, value in record.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
            else:
                factor_record = FactorStore(stock_code=stock_code, trade_date=trade_date, **record)
                self.db.add(factor_record)

        self.db.commit()
        logger.info(f"因子数据保存完成: {len(records)} 条")