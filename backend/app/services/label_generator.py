"""标签生成器 - 计算未来20日收益率"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from app.models.stock_daily import StockDaily
from app.utils.date_utils import get_next_n_trade_days


class LabelGenerator:
    """标签生成器"""

    def __init__(self, db: Session):
        self.db = db

    def generate_labels(self, trade_date: str) -> pd.DataFrame:
        """生成未来20日收益率标签"""
        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()

        # 获取当日所有股票收盘价
        current = (
            self.db.query(StockDaily.stock_code, StockDaily.close)
            .filter(StockDaily.trade_date == trade_date_dt)
            .all()
        )

        labels = []
        for stock_code, close in current:
            if not close:
                continue

            # 查找20个交易日后的数据
            future_date = trade_date_dt
            for _ in range(30):  # 最多找30个自然日
                future_date += timedelta(days=1)
                future_record = (
                    self.db.query(StockDaily.close)
                    .filter(
                        StockDaily.stock_code == stock_code,
                        StockDaily.trade_date == future_date,
                    )
                    .first()
                )
                if future_record and future_record[0]:
                    future_close = float(future_record[0])
                    future_return = (future_close / float(close) - 1) * 100
                    labels.append({
                        "stock_code": stock_code,
                        "trade_date": trade_date_dt,
                        "future_return_20d": future_return,
                    })
                    break

        df = pd.DataFrame(labels)
        logger.info(f"标签生成完成: {len(df)} 条")
        return df

    def generate_classification_labels(self, returns: pd.Series, threshold: float = 0.0) -> pd.Series:
        """将收益率转换为分类标签"""
        return (returns > threshold).astype(int)