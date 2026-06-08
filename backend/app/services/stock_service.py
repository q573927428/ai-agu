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

    def list_stocks(self, page: int = 1, page_size: int = 10) -> tuple:
        """分页获取所有股票列表（含最新行情和估值数据）"""
        from app.models.factor import FactorStore
        from sqlalchemy import func

        # 1. 分页查询股票基础信息
        query = self.db.query(StockBasic).filter(StockBasic.is_active == 1).order_by(StockBasic.stock_code)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        codes = [s.stock_code for s in items]
        exchange_map = {
            "SSE": "SH",
            "SZSE": "SZ",
            "BSE": "BJ",
        }

        daily_map = {}
        factor_map = {}

        if codes:
            # 2. 子查询：每个股票代码的最新交易日
            latest_daily_sub = (
                self.db.query(
                    StockDaily.stock_code,
                    func.max(StockDaily.trade_date).label("max_date")
                )
                .filter(StockDaily.stock_code.in_(codes))
                .group_by(StockDaily.stock_code)
                .subquery()
            )

            # 3. 关联查询最新日行情（只需返回列，不用取所有行再 Python 去重）
            daily_rows = (
                self.db.query(StockDaily)
                .join(
                    latest_daily_sub,
                    (StockDaily.stock_code == latest_daily_sub.c.stock_code)
                    & (StockDaily.trade_date == latest_daily_sub.c.max_date)
                )
                .all()
            )
            daily_map = {d.stock_code: d for d in daily_rows}

            # 4. 子查询：每个股票代码的最新因子交易日
            latest_factor_sub = (
                self.db.query(
                    FactorStore.stock_code,
                    func.max(FactorStore.trade_date).label("max_date")
                )
                .filter(FactorStore.stock_code.in_(codes))
                .group_by(FactorStore.stock_code)
                .subquery()
            )

            # 5. 关联查询最新因子数据
            factor_rows = (
                self.db.query(FactorStore)
                .join(
                    latest_factor_sub,
                    (FactorStore.stock_code == latest_factor_sub.c.stock_code)
                    & (FactorStore.trade_date == latest_factor_sub.c.max_date)
                )
                .all()
            )
            factor_map = {f.stock_code: f for f in factor_rows}

        # 6. 组装返回数据
        enriched = []
        for s in items:
            daily = daily_map.get(s.stock_code)
            factor = factor_map.get(s.stock_code)
            exchange_tag = exchange_map.get(s.exchange, s.exchange)
            enriched.append({
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "industry": s.industry,
                "area": s.area,
                "exchange": exchange_tag,
                "list_date": str(s.list_date) if s.list_date else None,
                "close_price": float(daily.close) if daily and daily.close else None,
                "pct_chg": float(daily.pct_chg) if daily and daily.pct_chg else None,
                "pe_ttm": float(factor.stock_pe_ttm) if factor and factor.stock_pe_ttm is not None else None,
                "pb": float(factor.stock_pb) if factor and factor.stock_pb is not None else None,
                "turnover_rate": float(factor.stock_turnover_rate_5d) if factor and factor.stock_turnover_rate_5d is not None else None,
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