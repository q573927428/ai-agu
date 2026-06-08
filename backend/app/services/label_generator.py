"""标签生成器 - 计算次日收益率"""
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
        """生成次日收益率标签（使用pct_chg涨跌幅）"""
        trade_date_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
        next_date = trade_date_dt + timedelta(days=1)

        # 获取当日所有股票的次日涨跌幅
        rows = (
            self.db.query(StockDaily.stock_code, StockDaily.pct_chg)
            .filter(StockDaily.trade_date == next_date)
            .all()
        )

        labels = []
        for stock_code, pct_chg in rows:
            if pct_chg is None:
                continue
            # pct_chg 已经是百分数（如 5.0 = 5%），直接作为标签
            labels.append({
                "stock_code": stock_code,
                "trade_date": trade_date_dt,
                "future_return_1d": float(pct_chg),
            })

        df = pd.DataFrame(labels)
        logger.info(f"标签生成完成: {len(df)} 条")
        return df

    def generate_classification_labels(self, returns: pd.Series, threshold: float = 0.0) -> pd.Series:
        """将收益率转换为分类标签"""
        return (returns > threshold).astype(int)