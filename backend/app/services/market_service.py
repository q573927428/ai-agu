"""市场概览服务"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from typing import Optional
from app.models.stock_daily import StockDaily
from app.models.index_daily import IndexDaily
from app.models.model_record import ModelRecord


class MarketService:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_trade_date(self) -> Optional[date]:
        """获取最新交易日"""
        result = (
            self.db.query(func.max(StockDaily.trade_date))
            .scalar()
        )
        return result

    def get_market_overview(self) -> dict:
        """获取市场概览"""
        latest_date = self.get_latest_trade_date()
        if not latest_date:
            return self._empty_overview()

        # 1. 获取指数数据（上证指数 000001.SH + 深证成指 399001.SZ）
        index_ts_codes = ["000001.SH", "399001.SZ"]
        index_records = (
            self.db.query(IndexDaily)
            .filter(
                IndexDaily.ts_code.in_(index_ts_codes),
                IndexDaily.trade_date == latest_date,
            )
            .all()
        )
        index_map = {r.ts_code: r for r in index_records}

        sh = index_map.get("000001.SH")
        sz = index_map.get("399001.SZ")

        # 2. 统计涨跌家数（从 stock_daily 获取全市场个股数据，不含指数）
        stats = self._get_market_stats(latest_date)

        # 3. 获取模型状态
        model_status = self._get_model_status()

        return {
            "market_index": {
                "sh_index": float(sh.close) if sh else None,
                "sh_change": float(sh.pct_chg) if sh else None,
                "sz_index": float(sz.close) if sz else None,
                "sz_change": float(sz.pct_chg) if sz else None,
            },
            "market_stats": stats,
            "top_industries": [],
            "model_status": model_status,
        }

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
        """获取模型状态"""
        active_model = (
            self.db.query(ModelRecord)
            .filter(ModelRecord.is_active == 1)
            .order_by(ModelRecord.train_date.desc())
            .first()
        )

        if not active_model:
            # 尝试获取最新训练的模型
            latest_model = (
                self.db.query(ModelRecord)
                .order_by(ModelRecord.train_date.desc())
                .first()
            )

            if not latest_model:
                return {
                    "model_version": "",
                    "last_train_date": None,
                    "latest_ic": 0,
                    "is_active": False,
                }

            return {
                "model_version": latest_model.model_version,
                "last_train_date": str(latest_model.train_date) if latest_model.train_date else None,
                "latest_ic": float(latest_model.valid_ic) if latest_model.valid_ic else 0,
                "is_active": False,
            }

        return {
            "model_version": active_model.model_version,
            "last_train_date": str(active_model.train_date) if active_model.train_date else None,
            "latest_ic": float(active_model.valid_ic) if active_model.valid_ic else 0,
            "is_active": True,
        }

    def _empty_overview(self) -> dict:
        """返回空概览"""
        return {
            "market_index": {
                "sh_index": None,
                "sh_change": None,
                "sz_index": None,
                "sz_change": None,
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