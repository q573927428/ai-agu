"""市场概览服务"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from typing import Optional
from loguru import logger
from app.models.stock_daily import StockDaily
from app.models.index_daily import IndexDaily
from app.models.model_record import ModelRecord
from app.services.data_fetcher import DataFetcher
from app.utils.date_utils import is_trade_day


class MarketService:
    def __init__(self, db: Session):
        self.db = db
        self.fetcher = DataFetcher()

    def get_latest_trade_date(self) -> Optional[date]:
        """获取数据库中最新的交易日"""
        result = (
            self.db.query(func.max(StockDaily.trade_date))
            .scalar()
        )
        return result

    def is_trading_time(self) -> bool:
        """判断当前是否在 A 股交易时段内（9:30-15:00 工作日）"""
        now = datetime.now()
        if not is_trade_day(now):
            return False
        hour, minute = now.hour, now.minute
        time_val = hour * 100 + minute
        return (930 <= time_val < 1130) or (1300 <= time_val < 1500)

    def get_market_overview(self) -> dict:
        """获取市场概览
        - 数据库有当日数据 → 读取数据库
        - 数据库无当日数据且为交易时段 → 从 AkShare 拉取实时行情
        - 非交易时段且无当日数据 → 返回最近一个交易日的历史数据
        """
        latest_date = self.get_latest_trade_date()
        today = date.today()
        now = datetime.now()

        # 判断是否使用实时数据
        use_realtime = (
            self.is_trading_time() and
            (latest_date is None or latest_date < today)
        )

        if use_realtime:
            logger.info("交易时段内无当日收盘数据，切换到 AkShare 实时行情")
            return self._get_realtime_overview()

        # 从数据库读取（有当日数据就用当日，否则用最近交易日）
        if not latest_date:
            return self._empty_overview()

        return self._get_db_overview(latest_date)

    def _get_db_overview(self, trade_date: date) -> dict:
        """从数据库获取市场概览"""
        # 1. 获取指数数据
        index_ts_codes = ["000001.SH", "399001.SZ", "399006.SZ", "000300.SH", "000905.SH", "000688.SH"]
        index_records = (
            self.db.query(IndexDaily)
            .filter(
                IndexDaily.ts_code.in_(index_ts_codes),
                IndexDaily.trade_date == trade_date,
            )
            .all()
        )
        index_map = {r.ts_code: r for r in index_records}

        sh = index_map.get("000001.SH")
        sz = index_map.get("399001.SZ")
        cyb = index_map.get("399006.SZ")
        hs300 = index_map.get("000300.SH")
        zz500 = index_map.get("000905.SH")
        kc50 = index_map.get("000688.SH")

        # 2. 涨跌家数
        stats = self._get_market_stats(trade_date)

        # 3. 模型状态
        model_status = self._get_model_status()

        return {
            "market_index": {
                "sh_index": float(sh.close) if sh else None,
                "sh_change": float(sh.pct_chg) if sh else None,
                "sz_index": float(sz.close) if sz else None,
                "sz_change": float(sz.pct_chg) if sz else None,
                "cyb_index": float(cyb.close) if cyb else None,
                "cyb_change": float(cyb.pct_chg) if cyb else None,
                "hs300_index": float(hs300.close) if hs300 else None,
                "hs300_change": float(hs300.pct_chg) if hs300 else None,
                "zz500_index": float(zz500.close) if zz500 else None,
                "zz500_change": float(zz500.pct_chg) if zz500 else None,
                "kc50_index": float(kc50.close) if kc50 else None,
                "kc50_change": float(kc50.pct_chg) if kc50 else None,
            },
            "market_stats": stats,
            "top_industries": [],
            "model_status": model_status,
        }

    def _get_realtime_overview(self) -> dict:
        """从 AkShare 实时行情获取市场概览（交易时段使用）"""
        import asyncio

        try:
            # 创建事件循环运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 并发获取指数实时行情 + 全市场个股实时行情
            index_df = loop.run_until_complete(self.fetcher.fetch_index_spot())
            spot_df = loop.run_until_complete(self.fetcher.fetch_stock_daily_batch(
                date.today().strftime("%Y-%m-%d")
            ))

            loop.close()

            # ---- 解析指数实时数据 ----
            # AkShare stock_zh_index_spot() 返回字段示例（含中文列名）:
            # 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额
            index_symbols = {
                "sh000001": "sh",    # 上证
                "sz399001": "sz",    # 深证
                "sz399006": "cyb",   # 创业板
                "sh000300": "hs300", # 沪深300
                "sh000905": "zz500", # 中证500
                "sh000688": "kc50",  # 科创50
            }

            market_index = {
                "sh_index": None, "sh_change": None,
                "sz_index": None, "sz_change": None,
                "cyb_index": None, "cyb_change": None,
                "hs300_index": None, "hs300_change": None,
                "zz500_index": None, "zz500_change": None,
                "kc50_index": None, "kc50_change": None,
            }

            if index_df is not None and not index_df.empty:
                for _, row in index_df.iterrows():
                    code = str(row.get("代码", ""))
                    key = index_symbols.get(code)
                    if key:
                        price = row.get("最新价")
                        pct = row.get("涨跌幅")
                        try:
                            market_index[f"{key}_index"] = float(price) if price is not None else None
                            market_index[f"{key}_change"] = float(pct) if pct is not None else None
                        except (ValueError, TypeError):
                            pass

            # ---- 解析实时涨跌家数 ----
            stats = {"up_count": 0, "down_count": 0, "flat_count": 0, "advance_decline_ratio": 0}

            if spot_df is not None and not spot_df.empty and "涨跌幅" in spot_df.columns:
                pct_col = "涨跌幅"
                for _, row in spot_df.iterrows():
                    pct_val = row.get(pct_col)
                    if pct_val is None:
                        continue
                    try:
                        pct = float(pct_val)
                        if pct > 0:
                            stats["up_count"] += 1
                        elif pct < 0:
                            stats["down_count"] += 1
                        else:
                            stats["flat_count"] += 1
                    except (ValueError, TypeError):
                        continue

                if stats["down_count"] > 0:
                    stats["advance_decline_ratio"] = round(stats["up_count"] / stats["down_count"], 4)

            # 模型状态（实时行情不需要模型状态）
            model_status = self._get_model_status()

            logger.info(f"实时行情拉取完成: 涨{stats['up_count']} 跌{stats['down_count']}")

            return {
                "market_index": market_index,
                "market_stats": stats,
                "top_industries": [],
                "model_status": model_status,
            }

        except Exception as e:
            logger.error(f"获取实时行情失败, 降级到数据库: {e}")
            # 降级到数据库
            latest_date = self.get_latest_trade_date()
            if latest_date:
                return self._get_db_overview(latest_date)
            return self._empty_overview()

    def _get_market_stats(self, trade_date: date) -> dict:
        """统计A股涨跌家数"""
        all_daily = (
            self.db.query(StockDaily)
            .filter(
                StockDaily.trade_date == trade_date,
                StockDaily.pct_chg.isnot(None),
            )
            .all()
        )

        up_count = 0
        down_count = 0
        flat_count = 0

        for row in all_daily:
            pct = float(row.pct_chg)
            if pct > 0:
                up_count += 1
            elif pct < 0:
                down_count += 1
            else:
                flat_count += 1

        advance_decline_ratio = round(up_count / down_count, 4) if down_count > 0 else 0

        return {
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "advance_decline_ratio": advance_decline_ratio,
        }

    def _get_model_status(self) -> dict:
        """获取模型状态（仅返回最新日期的模型）"""
        latest_date = (
            self.db.query(func.max(ModelRecord.train_date))
            .scalar()
        )

        if not latest_date:
            return {
                "model_version": "",
                "last_train_date": None,
                "latest_ic": 0,
                "is_active": False,
            }

        latest_models = (
            self.db.query(ModelRecord)
            .filter(ModelRecord.train_date == latest_date)
            .order_by(ModelRecord.id.desc())
            .all()
        )

        model_list = []
        for m in latest_models:
            model_list.append({
                "id": m.id,
                "model_version": m.model_version,
                "train_date": str(m.train_date) if m.train_date else None,
                "valid_ic": float(m.valid_ic) if m.valid_ic else 0,
                "num_samples": m.num_samples,
                "num_features": m.num_features,
                "is_active": bool(m.is_active),
            })

        active_model = next((m for m in latest_models if m.is_active == 1), None)
        latest_model = latest_models[0] if latest_models else None
        display_model = active_model or latest_model

        return {
            "model_version": display_model.model_version if display_model else "",
            "last_train_date": str(latest_date),
            "latest_ic": float(display_model.valid_ic) if display_model and display_model.valid_ic else 0,
            "is_active": bool(active_model is not None),
            "models": model_list,
        }

    def _empty_overview(self) -> dict:
        """返回空概览"""
        return {
            "market_index": {
                "sh_index": None,
                "sh_change": None,
                "sz_index": None,
                "sz_change": None,
                "cyb_index": None,
                "cyb_change": None,
                "hs300_index": None,
                "hs300_change": None,
                "zz500_index": None,
                "zz500_change": None,
                "kc50_index": None,
                "kc50_change": None,
            },
            "market_stats": {
                "up_count": 0,
                "down_count": 0,
                "flat_count": 0,
                "advance_decline_ratio": 0,
            },
            "top_industries": [],
            "model_status": {
                "model_version": "",
                "last_train_date": None,
                "latest_ic": 0,
                "is_active": False,
            },
        }