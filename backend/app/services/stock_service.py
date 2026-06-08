"""股票信息服务"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from app.models.stock import StockBasic
from app.models.stock_daily import StockDaily
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

    def get_latest_prediction(self, stock_code: str) -> Optional[Prediction]:
        """获取最新预测"""
        return (
            self.db.query(Prediction)
            .filter(Prediction.stock_code == stock_code)
            .order_by(Prediction.predict_date.desc())
            .first()
        )

    def search_stocks(self, keyword: str) -> List[StockBasic]:
        """搜索股票（按代码或名称）"""
        return (
            self.db.query(StockBasic)
            .filter(
                (StockBasic.stock_code.like(f"%{keyword}%"))
                | (StockBasic.stock_name.like(f"%{keyword}%"))
            )
            .limit(20)
            .all()
        )

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

        直接从 stock_basic 表读取最新行情快照，
        不需要再 JOIN stock_daily 和 factor_store 表。
        """
        from sqlalchemy import asc, desc, case

        exchange_map = {
            "SSE": "SH",
            "SZSE": "SZ",
            "BSE": "BJ",
        }

        # 1. 基础查询
        query = self.db.query(StockBasic).filter(StockBasic.is_active == 1)
        total = query.count()

        # 2. 排序
        sort_col_map = {
            "close_price": StockBasic.close_price,
            "pct_chg": StockBasic.pct_chg,
            "pe_ttm": StockBasic.pe_ttm,
            "pb": StockBasic.pb,
            "turnover_rate": StockBasic.turnover_rate,
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
        for s in rows:
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
                "pe_ttm": float(s.pe_ttm) if s.pe_ttm is not None else None,
                "pb": float(s.pb) if s.pb is not None else None,
                "turnover_rate": float(s.turnover_rate) if s.turnover_rate is not None else None,
            })
        return enriched, total

    def get_stock_detail(self, stock_code: str) -> dict:
        """获取股票详情"""
        basic = self.get_stock_basic(stock_code)
        daily = self.get_stock_daily(stock_code)
        prediction = self.get_latest_prediction(stock_code)

        return {
            "basic": basic,
            "latest_daily": daily,
            "latest_prediction": prediction,
        }

    def update_latest_snapshot(self, stock_code: str, trade_date: date,
                               close_price: Optional[float] = None,
                               pct_chg: Optional[float] = None,
                               pe_ttm: Optional[float] = None,
                               pb: Optional[float] = None,
                               turnover_rate: Optional[float] = None) -> None:
        """更新股票最新行情快照到 stock_basic 表"""
        self.db.query(StockBasic).filter(StockBasic.stock_code == stock_code).update({
            "trade_date": trade_date,
            "close_price": close_price,
            "pct_chg": pct_chg,
            "pe_ttm": pe_ttm,
            "pb": pb,
            "turnover_rate": turnover_rate,
        })
        self.db.commit()