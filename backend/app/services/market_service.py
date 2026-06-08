"""市场概览服务"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from typing import Optional
from loguru import logger
from app.models.stock_daily import StockDaily
from app.models.index_daily import IndexDaily
from app.models.model_record import ModelRecord


class MarketService:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_trade_date(self) -> Optional[date]:
        """获取数据库中最新的交易日"""
        result = (
            self.db.query(func.max(StockDaily.trade_date))
            .scalar()
        )
        return result

    def get_market_overview(self) -> dict:
        """获取市场概览

        数据全部从数据库读取，不涉及任何实时行情接口。
        index_daily / stock_daily 由定时任务在每日收盘后更新。
        """
        latest_date = self.get_latest_trade_date()
        if not latest_date:
            logger.warning("数据库无数据")
            return self._empty_overview()

        logger.info(f"从数据库读取市场概览: {latest_date}")
        return self._get_db_overview(latest_date)

    def _get_db_overview(self, trade_date: date) -> dict:
        """从数据库获取市场概览"""
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

        stats = self._get_market_stats(trade_date)
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

    def _get_market_stats(self, trade_date: date) -> dict:
        """统计A股涨跌家数（数据库）"""
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