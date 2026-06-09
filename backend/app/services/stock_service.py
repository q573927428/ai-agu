"""股票信息服务"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc, case
from typing import Optional, List
from datetime import date
from app.models.stock import StockBasic
from app.models.stock_daily import StockDaily
from app.models.stock_daily_basic import StockDailyBasic
from app.models.prediction import Prediction
from app.models.stock_event import StockEvent


class StockService:
    def __init__(self, db: Session):
        self.db = db

    def get_stock_basic(self, stock_code: str) -> Optional[StockBasic]:
        """获取股票基础信息"""
        return self.db.query(StockBasic).filter(StockBasic.stock_code == stock_code).first()

    def get_stock_daily(self, stock_code: str, trade_date: Optional[date] = None) -> Optional[StockDaily]:
        """获取股票日数据"""
        query = self.db.query(StockDaily).filter(StockDaily.stock_code == stock_code)
        if trade_date:
            query = query.filter(StockDaily.trade_date == trade_date)
        return query.order_by(StockDaily.trade_date.desc()).first()

    def get_latest_daily_basic(self, stock_code: str) -> Optional[StockDailyBasic]:
        """获取股票最新的 daily_basic 数据（基本面指标）"""
        return (
            self.db.query(StockDailyBasic)
            .filter(StockDailyBasic.stock_code == stock_code)
            .order_by(StockDailyBasic.trade_date.desc())
            .first()
        )

    def get_latest_prediction(self, stock_code: str) -> Optional[Prediction]:
        """获取最新预测"""
        return (
            self.db.query(Prediction)
            .filter(Prediction.stock_code == stock_code)
            .order_by(Prediction.predict_date.desc())
            .first()
        )

    def search_stocks(self, keyword: str) -> list:
        """搜索股票（按代码或名称），关联 stock_daily_basic 获取基本面数据"""
        exchange_map = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}

        # 相关子查询：获取每只股票的最新预测收益率和置信度
        latest_return_subq = (
            self.db.query(Prediction.predicted_return)
            .filter(Prediction.stock_code == StockBasic.stock_code)
            .order_by(Prediction.predict_date.desc())
            .limit(1)
            .correlate(StockBasic)
            .label("predicted_return")
        )
        latest_conf_subq = (
            self.db.query(Prediction.confidence)
            .filter(Prediction.stock_code == StockBasic.stock_code)
            .order_by(Prediction.predict_date.desc())
            .limit(1)
            .correlate(StockBasic)
            .label("confidence")
        )

        rows = (
            self.db.query(StockBasic, StockDailyBasic, latest_return_subq, latest_conf_subq)
            .outerjoin(
                StockDailyBasic,
                (StockBasic.stock_code == StockDailyBasic.stock_code)
                & (StockDailyBasic.trade_date == StockBasic.trade_date)
            )
            .filter(
                (StockBasic.stock_code.like(f"%{keyword}%"))
                | (StockBasic.stock_name.like(f"%{keyword}%"))
            )
            .limit(20)
            .all()
        )

        results = []
        for s, d, predicted_return, confidence in rows:
            exchange_tag = exchange_map.get(s.exchange, s.exchange)
            results.append({
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "industry": s.industry,
                "exchange": exchange_tag,
                "close_price": float(s.close_price) if s.close_price is not None else None,
                "pct_chg": float(s.pct_chg) if s.pct_chg is not None else None,
                "pe_ttm": float(d.pe_ttm) if d and d.pe_ttm else None,
                "pb": float(d.pb) if d and d.pb else None,
                "turnover_rate": float(d.turnover_rate) if d and d.turnover_rate is not None else None,
                "volume_ratio": float(d.volume_ratio) if d and d.volume_ratio is not None else None,
                "ps_ttm": float(d.ps_ttm) if d and d.ps_ttm else None,
                "dv_ratio": float(d.dv_ratio) if d and d.dv_ratio else None,
                "total_mv": float(d.total_mv) if d and d.total_mv else None,
                "trade_date": str(s.trade_date) if s.trade_date else None,
                "predicted_return": float(predicted_return) if predicted_return is not None else None,
                "confidence": float(confidence) if confidence is not None else None,
            })
        return results

    def get_stock_daily_history(self, stock_code: str, limit: int = 120) -> list:
        """获取股票日K线历史数据（用于绘制K线图）"""
        records = (
            self.db.query(StockDaily)
            .filter(StockDaily.stock_code == stock_code)
            .order_by(StockDaily.trade_date.desc())
            .limit(limit)
            .all()
        )
        # 按日期升序返回（K线图需要从左到右从旧到新）
        records.reverse()
        return records

    def get_stock_events(self, stock_code: str) -> list:
        """获取股票事件（分红送股等）"""
        records = (
            self.db.query(StockEvent)
            .filter(StockEvent.stock_code == stock_code)
            .order_by(StockEvent.ex_date.asc())
            .all()
        )
        return [r.to_dict() for r in records]

    def list_stocks(self, page: int = 1, page_size: int = 10, sort_by: Optional[str] = None, sort_order: str = "asc") -> tuple:
        """分页获取所有股票列表（含最新行情和估值数据）

        行情快照从 stock_basic 表读取，
        基本面指标（pe_ttm/pb/turnover_rate 等）从 stock_daily_basic 表读取。
        """
        exchange_map = {
            "SSE": "SH",
            "SZSE": "SZ",
            "BSE": "BJ",
        }

        # 相关子查询：获取每只股票的最新预测收益率和置信度
        latest_return_subq = (
            self.db.query(Prediction.predicted_return)
            .filter(Prediction.stock_code == StockBasic.stock_code)
            .order_by(Prediction.predict_date.desc())
            .limit(1)
            .correlate(StockBasic)
            .label("predicted_return")
        )
        latest_conf_subq = (
            self.db.query(Prediction.confidence)
            .filter(Prediction.stock_code == StockBasic.stock_code)
            .order_by(Prediction.predict_date.desc())
            .limit(1)
            .correlate(StockBasic)
            .label("confidence")
        )

        # 1. 基础查询 — LEFT JOIN stock_daily_basic 获取最新基本面数据，加相关子查询获取最新预测
        query = (
            self.db.query(StockBasic, StockDailyBasic, latest_return_subq, latest_conf_subq)
            .outerjoin(
                StockDailyBasic,
                (StockBasic.stock_code == StockDailyBasic.stock_code)
                & (StockDailyBasic.trade_date == StockBasic.trade_date)
            )
            .filter(StockBasic.is_active == 1)
        )

        # count 用独立查询（避免 JOIN 影响计数值）
        total_query = self.db.query(StockBasic).filter(StockBasic.is_active == 1)
        total = total_query.count()

        # 2. 排序 — 支持从两个表取排序字段（含预测相关子查询字段）
        sort_col_map = {
            "close_price": StockBasic.close_price,
            "pct_chg": StockBasic.pct_chg,
            "pe_ttm": StockDailyBasic.pe_ttm,
            "pb": StockDailyBasic.pb,
            "turnover_rate": StockDailyBasic.turnover_rate,
            "volume_ratio": StockDailyBasic.volume_ratio,
            "ps_ttm": StockDailyBasic.ps_ttm,
            "dv_ratio": StockDailyBasic.dv_ratio,
            "total_mv": StockDailyBasic.total_mv,
            "predicted_return": latest_return_subq,
            "confidence": latest_conf_subq,
        }
        order_func = asc if sort_order == "asc" else desc

        if sort_by in sort_col_map:
            col = sort_col_map[sort_by]
            nulls_last = case((col.is_(None), 1), else_=0)
            query = query.order_by(nulls_last, order_func(col), StockBasic.stock_code)
        else:
            query = query.order_by(StockBasic.stock_code)

        # 3. 分页
        rows = query.offset((page - 1) * page_size).limit(page_size).all()

        # 4. 组装返回
        enriched = []
        for s, d, predicted_return, confidence in rows:
            exchange_tag = exchange_map.get(s.exchange, s.exchange)
            enriched.append({
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "industry": s.industry,
                "area": s.area,
                "exchange": exchange_tag,
                "list_date": str(s.list_date) if s.list_date else None,
                "trade_date": str(s.trade_date) if s.trade_date else None,
                "close_price": float(s.close_price) if s.close_price is not None else None,
                "pct_chg": float(s.pct_chg) if s.pct_chg is not None else None,
                "pe_ttm": float(d.pe_ttm) if d and d.pe_ttm else None,
                "pb": float(d.pb) if d and d.pb else None,
                "turnover_rate": float(d.turnover_rate) if d and d.turnover_rate is not None else None,
                "volume_ratio": float(d.volume_ratio) if d and d.volume_ratio is not None else None,
                "ps_ttm": float(d.ps_ttm) if d and d.ps_ttm else None,
                "dv_ratio": float(d.dv_ratio) if d and d.dv_ratio else None,
                "total_mv": float(d.total_mv) if d and d.total_mv else None,
                "predicted_return": float(predicted_return) if predicted_return is not None else None,
                "confidence": float(confidence) if confidence is not None else None,
            })
        return enriched, total

    def get_stock_detail(self, stock_code: str) -> dict:
        """获取股票详情（含 daily_basic 基本面数据）"""
        basic = self.get_stock_basic(stock_code)
        daily = self.get_stock_daily(stock_code)
        daily_basic = self.get_latest_daily_basic(stock_code)
        prediction = self.get_latest_prediction(stock_code)

        return {
            "basic": basic,
            "latest_daily": daily,
            "latest_daily_basic": daily_basic,
            "latest_prediction": prediction,
        }

    def update_latest_snapshot(self, stock_code: str, trade_date: date,
                               close_price: Optional[float] = None,
                               pct_chg: Optional[float] = None) -> None:
        """更新股票最新行情快照到 stock_basic 表（仅更新行情字段，基本面指标从 daily_basic 表读取）"""
        self.db.query(StockBasic).filter(StockBasic.stock_code == stock_code).update({
            "trade_date": trade_date,
            "close_price": close_price,
            "pct_chg": pct_chg,
        })
        self.db.commit()