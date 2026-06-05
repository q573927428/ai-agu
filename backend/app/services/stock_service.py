"""股票信息服务"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from app.models.stock import StockBasic
from app.models.stock_daily import StockDaily
from app.models.prediction import Prediction


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