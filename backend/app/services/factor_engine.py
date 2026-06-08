"""因子计算引擎 - 优化版：批量查询消除N+1"""
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.factor import FactorStore
from app.models.stock_daily import StockDaily
from app.models.macro import MacroData
from app.models.fina_indicator import FinaIndicator
from app.models.income import Income
from app.models.balancesheet import Balancesheet
from app.models.stock import StockBasic


class FactorEngine:
    """因子计算引擎 - 计算全部55个因子"""

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

    # ==================== 宏观因子 ====================

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

    # ==================== 市场因子 ====================

    def compute_market_factors(self, trade_date: str) -> pd.Series:
        """计算市场因子 - 基于全市场股票数据"""
        from app.utils.date_utils import get_previous_n_trade_days

        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        past_dates = get_previous_n_trade_days(trade_date_dt, 20)

        # 获取全市场当日数据
        current_records = (
            self.db.query(StockDaily.stock_code, StockDaily.close, StockDaily.volume,
                          StockDaily.amount, StockDaily.pct_chg)
            .filter(StockDaily.trade_date == trade_date_dt.date())
            .all()
        )

        # 获取历史数据用于计算市场指数
        historical = (
            self.db.query(StockDaily.trade_date, StockDaily.close, StockDaily.volume,
                          StockDaily.amount, StockDaily.pct_chg)
            .filter(StockDaily.trade_date.in_([d.date() for d in past_dates]))
            .all()
        )

        # 按日期组织数据
        hist_by_date = {}
        for r in historical:
            dt = r.trade_date
            if dt not in hist_by_date:
                hist_by_date[dt] = {"closes": [], "volumes": [], "amounts": [], "pct_chgs": []}
            if r.close:
                hist_by_date[dt]["closes"].append(float(r.close))
            if r.volume:
                hist_by_date[dt]["volumes"].append(float(r.volume))
            if r.amount:
                hist_by_date[dt]["amounts"].append(float(r.amount))
            if r.pct_chg is not None:
                hist_by_date[dt]["pct_chgs"].append(float(r.pct_chg))

        # 按日期排序
        sorted_dates = sorted(hist_by_date.keys())
        if not sorted_dates:
            return pd.Series({
                "market_idx_return_5d": 0, "market_idx_return_20d": 0,
                "market_idx_volatility_20d": 0, "market_turnover_ma5": 0,
                "market_advance_decline_ratio": 1, "market_volume_ratio": 1,
                "market_breadth_20d": 0, "market_vix_proxy": 0,
                "market_style_momentum": 0, "market_style_value": 0,
            })

        # 市场指数收益率（等权平均价格作为指数代理）
        date_avg_prices = {}
        for dt in sorted_dates:
            closes = hist_by_date[dt]["closes"]
            if closes:
                date_avg_prices[dt] = np.mean(closes)

        avg_prices_arr = np.array(list(date_avg_prices.values()))
        returns = np.diff(avg_prices_arr) / avg_prices_arr[:-1] if len(avg_prices_arr) > 1 else np.array([0])

        # M01: 市场指数5日收益率
        market_return_5d = float(avg_prices_arr[-1] / avg_prices_arr[-min(6, len(avg_prices_arr))] - 1) if len(avg_prices_arr) >= 6 else 0

        # M02: 市场指数20日收益率
        market_return_20d = float(avg_prices_arr[-1] / avg_prices_arr[0] - 1) if len(avg_prices_arr) >= 2 else 0

        # M03: 市场指数20日年化波动率
        market_volatility_20d = float(np.std(returns) * np.sqrt(252)) if len(returns) >= 2 else 0

        # M04: 市场5日平均换手率（用涨跌幅绝对值代理）
        recent_pct_chgs = []
        for dt in sorted_dates[-5:]:
            recent_pct_chgs.extend(hist_by_date[dt]["pct_chgs"])
        market_turnover_ma5 = float(np.mean(np.abs(recent_pct_chgs))) if recent_pct_chgs else 0

        # M05: 市场涨跌比
        current_pct_chgs = [float(r.pct_chg) for r in current_records if r.pct_chg is not None]
        advance = sum(1 for c in current_pct_chgs if c > 0)
        decline = sum(1 for c in current_pct_chgs if c < 0)
        advance_decline_ratio = float(advance / decline) if decline > 0 else float(advance + 1)

        # M06: 市场量比
        current_volumes = [float(r.volume) for r in current_records if r.volume]
        current_volume_sum = np.sum(current_volumes) if current_volumes else 1
        hist_volume_sums = [np.sum(hist_by_date[dt]["volumes"]) for dt in sorted_dates[-5:]] if len(sorted_dates) >= 5 else [1]
        avg_hist_volume = np.mean(hist_volume_sums) if hist_volume_sums else 1
        volume_ratio = float(current_volume_sum / avg_hist_volume) if avg_hist_volume > 0 else 1

        # M07: 市场20日宽度指标
        if current_pct_chgs:
            n_high = sum(1 for c in current_pct_chgs if c > 3)
            n_low = sum(1 for c in current_pct_chgs if c < -3)
            n_total = len(current_pct_chgs)
            breadth_20d = float((n_high - n_low) / n_total) if n_total > 0 else 0
        else:
            breadth_20d = 0

        # M08: 市场恐慌指数代理（个股涨跌幅横截面标准差/均值）
        vix_proxy = float(np.std(current_pct_chgs)) if current_pct_chgs else 0

        # M09: 市场风格动量因子（大市值股票相对表现）
        if current_records:
            closes_sorted = sorted([float(r.close) for r in current_records if r.close], reverse=True)
            if len(closes_sorted) >= 20:
                top10_returns = np.mean([float(r.pct_chg or 0) for r in current_records
                                         if r.close and float(r.close) >= closes_sorted[len(closes_sorted)//10]])
                bottom10_returns = np.mean([float(r.pct_chg or 0) for r in current_records
                                             if r.close and float(r.close) <= closes_sorted[-len(closes_sorted)//10]])
                style_momentum = float(top10_returns - bottom10_returns) if bottom10_returns != 0 else 0
            else:
                style_momentum = 0
        else:
            style_momentum = 0

        # M10: 市场风格价值因子（低PE相对表现）
        style_value = style_momentum * 0.5  # 简化计算

        return pd.Series({
            "market_idx_return_5d": market_return_5d,
            "market_idx_return_20d": market_return_20d,
            "market_idx_volatility_20d": market_volatility_20d,
            "market_turnover_ma5": market_turnover_ma5,
            "market_advance_decline_ratio": advance_decline_ratio,
            "market_volume_ratio": volume_ratio,
            "market_breadth_20d": breadth_20d,
            "market_vix_proxy": vix_proxy,
            "market_style_momentum": style_momentum,
            "market_style_value": style_value,
        })

    # ==================== 行业因子 ====================

    def compute_industry_factors(self, trade_date: str, stock_codes: list = None) -> dict:
        """计算行业因子 - 按行业分组计算（批量优化版）

        Args:
            trade_date: 交易日期
            stock_codes: 限制计算的股票列表（不传则计算全部）
        """
        from app.utils.date_utils import get_previous_n_trade_days

        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        past_dates_20 = get_previous_n_trade_days(trade_date_dt, 20)

        # 获取所有股票及其行业
        stocks = self.db.query(StockBasic.stock_code, StockBasic.industry).all()
        stock_industry = {}
        for code, ind in stocks:
            if ind:
                stock_industry[code] = ind

        if not stock_industry:
            return {}

        # 如果传入了 stock_codes，只处理这些股票的行业
        if stock_codes:
            target_set = set(stock_codes)
            stock_industry = {k: v for k, v in stock_industry.items() if k in target_set}

        all_stock_codes = list(stock_industry.keys())
        if not all_stock_codes:
            return {}

        # 获取当日行情（只查需要的股票）
        current_quotes = (
            self.db.query(StockDaily.stock_code, StockDaily.close, StockDaily.pct_chg,
                          StockDaily.amount, StockDaily.volume)
            .filter(
                StockDaily.trade_date == trade_date_dt.date(),
                StockDaily.stock_code.in_(all_stock_codes),
            )
            .all()
        )

        current_by_code = {}
        for q in current_quotes:
            current_by_code[q.stock_code] = q

        # 获取历史行情（20日）
        hist_quotes_20 = (
            self.db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.close, StockDaily.pct_chg)
            .filter(
                StockDaily.stock_code.in_(all_stock_codes),
                StockDaily.trade_date.in_([d.date() for d in past_dates_20]),
            )
            .all()
        )

        # 【优化】预分组历史数据，避免O(N²)遍历
        hist_grouped: Dict[str, Dict] = {}
        for h in hist_quotes_20:
            if h.stock_code not in hist_grouped:
                hist_grouped[h.stock_code] = {}
            hist_grouped[h.stock_code][h.trade_date] = h

        # 【批量优化】一次性查询所有股票的最新财务指标
        latest_end_date_subq = (
            self.db.query(
                FinaIndicator.stock_code,
                func.max(FinaIndicator.end_date).label('max_end_date')
            )
            .filter(FinaIndicator.stock_code.in_(all_stock_codes))
            .group_by(FinaIndicator.stock_code)
            .subquery()
        )

        all_fina = (
            self.db.query(FinaIndicator)
            .join(
                latest_end_date_subq,
                (FinaIndicator.stock_code == latest_end_date_subq.c.stock_code) &
                (FinaIndicator.end_date == latest_end_date_subq.c.max_end_date)
            )
            .all()
        )

        fina_by_code = {}
        for f in all_fina:
            fina_by_code[f.stock_code] = f

        # 按行业分组汇总
        industry_data = {}
        for code, ind in stock_industry.items():
            if ind not in industry_data:
                industry_data[ind] = {
                    "codes": [],
                    "current_pct_chgs": [],
                    "current_amounts": [],
                    "hist_20d_returns": [],
                    "pe_vals": [],
                    "pb_vals": [],
                    "roe_vals": [],
                }
            industry_data[ind]["codes"].append(code)

            if code in current_by_code:
                q = current_by_code[code]
                if q.pct_chg is not None:
                    industry_data[ind]["current_pct_chgs"].append(float(q.pct_chg))
                if q.amount:
                    industry_data[ind]["current_amounts"].append(float(q.amount))

            # 历史20日收益率（直接查预分组字典，O(1)）
            code_hist = hist_grouped.get(code, {})
            dates_20 = sorted(code_hist.keys())
            if len(dates_20) >= 2:
                first_close = float(code_hist[dates_20[0]].close or 0)
                last_close = float(code_hist[dates_20[-1]].close or 0)
                if first_close > 0:
                    industry_data[ind]["hist_20d_returns"].append(last_close / first_close - 1)

            # 财务数据（批量已经查好）
            fina = fina_by_code.get(code)
            if fina and fina.eps and float(fina.eps) > 0 and code in current_by_code:
                if current_by_code[code].close:
                    pe = float(current_by_code[code].close) / float(fina.eps)
                    if 0 < pe < 1000:
                        industry_data[ind]["pe_vals"].append(pe)

            if fina and fina.bps and float(fina.bps) > 0 and code in current_by_code:
                if current_by_code[code].close:
                    pb = float(current_by_code[code].close) / float(fina.bps)
                    if 0 < pb < 100:
                        industry_data[ind]["pb_vals"].append(pb)

            if fina and fina.roe is not None:
                industry_data[ind]["roe_vals"].append(float(fina.roe))

        # 计算各行业因子
        industry_factors = {}
        for ind, data in industry_data.items():
            pct_chgs = data["current_pct_chgs"]
            returns_20d = data["hist_20d_returns"]

            return_5d = float(np.mean(pct_chgs)) if pct_chgs else 0
            return_20d = float(np.mean(returns_20d)) if returns_20d else 0
            vol = float(np.std(returns_20d)) if len(returns_20d) >= 2 else 0

            pe_vals = data["pe_vals"]
            pe_percentile = float(np.median(pe_vals) / 50) if pe_vals else 0.5
            pe_percentile = min(max(pe_percentile, 0), 1)

            pb_vals = data["pb_vals"]
            pb_percentile = float(np.median(pb_vals) / 10) if pb_vals else 0.5
            pb_percentile = min(max(pb_percentile, 0), 1)

            roe_median = float(np.median(data["roe_vals"])) if data["roe_vals"] else 0

            reversal_signal = -return_5d
            fund_flow = float(np.sum(data["current_amounts"])) if data["current_amounts"] else 0
            dispersion = float(np.std(pct_chgs)) if len(pct_chgs) >= 2 else 0

            industry_factors[ind] = {
                "industry_return_5d": return_5d,
                "industry_return_20d": return_20d,
                "industry_return_volatility": vol,
                "industry_pe_percentile": pe_percentile,
                "industry_pb_percentile": pb_percentile,
                "industry_roe_median": roe_median,
                "industry_momentum_rank": 0.5,  # 占位，下面统一计算
                "industry_reversal_signal": reversal_signal,
                "industry_fund_flow": fund_flow,
                "industry_dispersion": dispersion,
            }

        # 统一计算行业动量排名百分位
        all_returns_20d = [(ind, data["industry_return_20d"]) for ind, data in industry_factors.items()]
        all_returns_20d.sort(key=lambda x: x[1])
        total_inds = len(all_returns_20d)
        for rank, (ind_name, _) in enumerate(all_returns_20d):
            industry_factors[ind_name]["industry_momentum_rank"] = float((rank + 1) / total_inds) if total_inds > 0 else 0.5

        return industry_factors

    # ==================== 个股因子（批量版） ====================

    def _batch_load_historical_data(self, stock_codes: List[str], trade_date: str, days: int = 60) -> Dict[str, List]:
        """批量加载股票历史行情数据"""
        from app.utils.date_utils import get_previous_n_trade_days
        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        past_dates = get_previous_n_trade_days(trade_date_dt, days)

        records = (
            self.db.query(StockDaily)
            .filter(
                StockDaily.stock_code.in_(stock_codes),
                StockDaily.trade_date.in_([d.date() for d in past_dates]),
            )
            .order_by(StockDaily.stock_code, StockDaily.trade_date.asc())
            .all()
        )

        hist_data: Dict[str, List] = {}
        for r in records:
            code = r.stock_code
            if code not in hist_data:
                hist_data[code] = []
            hist_data[code].append(r)

        return hist_data

    def _batch_load_latest_fina(self, stock_codes: List[str]) -> Dict[str, FinaIndicator]:
        """批量加载每只股票的最新财务指标"""
        if not stock_codes:
            return {}

        latest_subq = (
            self.db.query(
                FinaIndicator.stock_code,
                func.max(FinaIndicator.end_date).label('max_end_date')
            )
            .filter(FinaIndicator.stock_code.in_(stock_codes))
            .group_by(FinaIndicator.stock_code)
            .subquery()
        )

        records = (
            self.db.query(FinaIndicator)
            .join(
                latest_subq,
                (FinaIndicator.stock_code == latest_subq.c.stock_code) &
                (FinaIndicator.end_date == latest_subq.c.max_end_date)
            )
            .all()
        )

        return {r.stock_code: r for r in records}

    def _batch_load_latest_balancesheet(self, stock_codes: List[str]) -> Dict[str, Balancesheet]:
        """批量加载每只股票的最新资产负债表"""
        if not stock_codes:
            return {}

        latest_subq = (
            self.db.query(
                Balancesheet.stock_code,
                func.max(Balancesheet.end_date).label('max_end_date')
            )
            .filter(Balancesheet.stock_code.in_(stock_codes))
            .group_by(Balancesheet.stock_code)
            .subquery()
        )

        records = (
            self.db.query(Balancesheet)
            .join(
                latest_subq,
                (Balancesheet.stock_code == latest_subq.c.stock_code) &
                (Balancesheet.end_date == latest_subq.c.max_end_date)
            )
            .all()
        )

        return {r.stock_code: r for r in records}

    def compute_stock_factors(self, stock_code: str, trade_date: str) -> dict:
        """个股因子计算（单只股票版，兼容旧调用）"""
        return self._compute_stock_factors_from_data(
            stock_code=stock_code,
            trade_date=trade_date,
            daily_records=None,
            fina=None,
            bs=None,
        )

    def _compute_stock_factors_from_data(
        self,
        stock_code: str,
        trade_date: str,
        daily_records: Optional[List] = None,
        fina: Optional[FinaIndicator] = None,
        bs: Optional[Balancesheet] = None,
    ) -> dict:
        """从已加载的数据计算单只股票因子"""
        from app.utils.date_utils import get_previous_n_trade_days

        if daily_records is None:
            # 兜底：如果没传数据，按原方式查
            trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d")
            past_dates = get_previous_n_trade_days(trade_date_dt, 60)
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

        latest = daily_records[-1]

        # 读取财务数据
        if fina is None:
            fina = (
                self.db.query(FinaIndicator)
                .filter(FinaIndicator.stock_code == stock_code)
                .order_by(FinaIndicator.end_date.desc())
                .first()
            )

        factors = {}

        # S01-S04: 收益率因子
        factors["stock_return_1d"] = float(returns[-1]) if len(returns) >= 1 else 0
        factors["stock_return_5d"] = float(closes_arr[-1] / closes_arr[-min(6, len(closes_arr))] - 1) if len(closes_arr) >= 6 else 0
        factors["stock_return_10d"] = float(closes_arr[-1] / closes_arr[-min(11, len(closes_arr))] - 1) if len(closes_arr) >= 11 else 0

        # S05-S06: 波动率因子
        factors["stock_volatility_20d"] = float(np.std(returns[-20:]) * np.sqrt(252)) if len(returns) >= 20 else 0
        factors["stock_volatility_60d"] = float(np.std(returns) * np.sqrt(252)) if len(returns) >= 2 else 0

        # S06: 量比
        vol_5 = np.mean(volumes[-5:]) if len(volumes) >= 5 else 0
        vol_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else (vol_5 or 1)
        factors["stock_volume_ratio_5d"] = float(vol_5 / vol_20) if vol_20 > 0 else 1

        # S07: 换手率
        factors["stock_turnover_rate_5d"] = float(np.mean(turnovers[-5:])) if len(turnovers) >= 5 else 0

        # S08: PE-TTM
        eps_val = float(fina.eps) if fina and fina.eps and float(fina.eps) > 0 else 0
        close_val = float(latest.close) if latest.close else 0
        if eps_val > 0 and close_val > 0:
            factors["stock_pe_ttm"] = float(close_val / eps_val)
        else:
            factors["stock_pe_ttm"] = 0

        # S09: PB
        bps_val = float(fina.bps) if fina and fina.bps and float(fina.bps) > 0 else 0
        if bps_val > 0 and close_val > 0:
            factors["stock_pb"] = float(close_val / bps_val)
        else:
            factors["stock_pb"] = 0

        # S10: PS-TTM
        factors["stock_ps_ttm"] = 0

        # S11: ROE
        factors["stock_roe_ttm"] = float(fina.roe) if fina and fina.roe is not None else 0

        # S12: ROA
        factors["stock_roa_ttm"] = float(fina.roa) if fina and fina.roa is not None else 0

        # S13: 营收同比增速
        factors["stock_revenue_yoy"] = float(fina.revenue_yoy) if fina and fina.revenue_yoy is not None else 0

        # S14: 净利润同比增速
        factors["stock_profit_yoy"] = float(fina.net_profit_yoy) if fina and fina.net_profit_yoy is not None else 0

        # S15: 毛利率
        factors["stock_gross_margin"] = float(fina.gross_margin) if fina and fina.gross_margin is not None else 0

        # S16: 资产负债率
        factors["stock_debt_ratio"] = float(fina.debt_ratio) if fina and fina.debt_ratio is not None else 0

        # S17: 20日动量
        factors["stock_momentum_20d"] = float(closes_arr[-2] / closes_arr[-min(21, len(closes_arr))] - 1) if len(closes_arr) >= 21 else 0

        # S18: 5日反转
        factors["stock_reversal_5d"] = -factors["stock_return_5d"]

        # S19: 规模因子
        if bs is None:
            bs = (
                self.db.query(Balancesheet)
                .filter(Balancesheet.stock_code == stock_code)
                .order_by(Balancesheet.end_date.desc())
                .first()
            )
        if bs and bs.cap_stk and close_val > 0:
            total_shares = float(bs.cap_stk)
            market_cap = close_val * total_shares
            factors["stock_size_factor"] = float(np.log(market_cap)) if market_cap > 0 else 0
        else:
            factors["stock_size_factor"] = 0

        # S20: 非流动性
        if len(returns) >= 20 and len(amounts) >= 20:
            amt_arr = np.array(amounts[-20:], dtype=float)
            ret_arr = np.abs(returns[-20:])
            with np.errstate(divide='ignore', invalid='ignore'):
                illiq_vals = ret_arr / (amt_arr / 1e8)
                illiq_vals = illiq_vals[~np.isinf(illiq_vals) & ~np.isnan(illiq_vals)]
            factors["stock_illiquidity"] = float(np.mean(illiq_vals)) if len(illiq_vals) > 0 else 0
        else:
            factors["stock_illiquidity"] = 0

        return factors

    # ==================== 主入口（批量优化版） ====================

    def compute_all(self, trade_date: str, top_n: int = 0) -> pd.DataFrame:
        """计算全市场全部因子（批量优化版）

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

        if not stocks:
            return pd.DataFrame()

        stock_codes = [s[0] for s in stocks]

        # 预计算宏观因子（所有股票共享）
        macro_factors = self.compute_macro_factors(trade_date)
        market_factors = self.compute_market_factors(trade_date)
        # 只计算这 N 只股票所属的行业因子
        industry_factors = self.compute_industry_factors(trade_date, stock_codes=stock_codes)

        # 获取股票行业映射
        stock_industry_map = {}
        stock_list = self.db.query(StockBasic.stock_code, StockBasic.industry).all()
        for code, ind in stock_list:
            if ind:
                stock_industry_map[code] = ind

        # ====== 批量加载数据 ======
        logger.info(f"批量加载 {len(stock_codes)} 只股票的历史行情数据...")
        hist_data = self._batch_load_historical_data(stock_codes, trade_date)

        logger.info(f"批量加载 {len(stock_codes)} 只股票的财务数据...")
        fina_data = self._batch_load_latest_fina(stock_codes)

        logger.info(f"批量加载 {len(stock_codes)} 只股票的资产负债表...")
        bs_data = self._batch_load_latest_balancesheet(stock_codes)
        # ==========================

        all_factors = []

        for stock_code in stock_codes:
            daily_records = hist_data.get(stock_code, [])
            if len(daily_records) < 5:
                continue

            stock_factors = self._compute_stock_factors_from_data(
                stock_code=stock_code,
                trade_date=trade_date,
                daily_records=daily_records,
                fina=fina_data.get(stock_code),
                bs=bs_data.get(stock_code),
            )
            if not stock_factors:
                continue

            # 行业因子
            industry = stock_industry_map.get(stock_code, "")
            industry_row = industry_factors.get(industry, {
                "industry_return_5d": 0, "industry_return_20d": 0,
                "industry_return_volatility": 0, "industry_pe_percentile": 0.5,
                "industry_pb_percentile": 0.5, "industry_roe_median": 0,
                "industry_momentum_rank": 0.5, "industry_reversal_signal": 0,
                "industry_fund_flow": 0, "industry_dispersion": 0,
            })

            row = {
                "stock_code": stock_code,
                "trade_date": trade_date,
                **macro_factors.to_dict(),
                **market_factors.to_dict(),
                **industry_row,
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