"""LightGBM训练器"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session
from sklearn.model_selection import train_test_split
from app.ml.model import LightGBMModel
from app.models.factor import FactorStore
from app.models.model_record import ModelRecord
from app.models.stock_daily import StockDaily
from app.config import settings


class Trainer:
    """LightGBM训练器"""

    def __init__(self, db: Session):
        self.db = db
        self.model = LightGBMModel()

    def prepare_training_data(self, start_date: str, end_date: str) -> tuple:
        """准备训练数据"""
        # 获取因子数据
        factors = (
            self.db.query(FactorStore)
            .filter(FactorStore.trade_date.between(start_date, end_date))
            .all()
        )

        if not factors:
            logger.warning(f"在 {start_date} ~ {end_date} 范围内没有因子数据")
            return None, None, None, None

        # 转换为 DataFrame
        records = []
        for f in factors:
            record = {
                "stock_code": f.stock_code,
                "trade_date": f.trade_date,
            }
            # 获取所有因子列（NULL填充为0，与预测时一致）
            for col in FactorStore.__table__.columns:
                if col.name in ("id", "stock_code", "trade_date", "created_at"):
                    continue
                val = getattr(f, col.name)
                record[col.name] = float(val) if val is not None else 0.0
            records.append(record)

        df = pd.DataFrame(records)

        # 获取标签 (未来20日收益率)
        labels = []
        for _, row in df.iterrows():
            stock_code = row["stock_code"]
            trade_date = row["trade_date"]

            # 找到20个交易日后的收盘价
            future = (
                self.db.query(StockDaily.close)
                .filter(
                    StockDaily.stock_code == stock_code,
                    StockDaily.trade_date > trade_date,
                )
                .order_by(StockDaily.trade_date)
                .limit(20)
                .all()
            )

            if len(future) == 20 and future[-1][0]:
                current_close = (
                    self.db.query(StockDaily.close)
                    .filter(
                        StockDaily.stock_code == stock_code,
                        StockDaily.trade_date == trade_date,
                    )
                    .scalar()
                )
                if current_close:
                    future_return = (float(future[-1][0]) / float(current_close) - 1) * 100
                    labels.append(future_return)
                else:
                    labels.append(None)
            else:
                labels.append(None)

        df["future_return_20d"] = labels
        df = df.dropna(subset=["future_return_20d"])

        if df.empty:
            return None, None, None, None

        # 特征列（排除非因子列）
        feature_cols = [c for c in df.columns if c not in ("stock_code", "trade_date", "future_return_20d")]

        X = df[feature_cols]
        y = df["future_return_20d"]

        # 按时间分割
        unique_dates = sorted(df["trade_date"].unique())
        split_idx = int(len(unique_dates) * 0.7)
        train_dates = unique_dates[:split_idx]
        valid_dates = unique_dates[split_idx:]

        train_mask = df["trade_date"].isin(train_dates)
        X_train = X[train_mask]
        y_train = y[train_mask]
        X_valid = X[~train_mask]
        y_valid = y[~train_mask]

        logger.info(f"训练数据: {len(X_train)} 条, 验证数据: {len(X_valid)} 条, 特征: {len(feature_cols)} 个")
        return X_train, y_train, X_valid, y_valid

    def train(self, start_date: str, end_date: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """训练模型"""
        result = self.prepare_training_data(start_date, end_date)
        if result[0] is None:
            return {"status": "failed", "message": "训练数据不足"}

        X_train, y_train, X_valid, y_valid = result

        # 训练
        train_result = self.model.train(X_train, y_train, X_valid, y_valid, params)
        train_result["num_samples"] = len(X_train)
        train_result["num_features"] = len(X_train.columns)

        # 保存模型
        model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        model_path = os.path.join(settings.model_dir, f"model_{model_version}.txt")
        os.makedirs(settings.model_dir, exist_ok=True)
        self.model.save_model(model_path)

        # 特征重要性
        feature_importance = self.model.get_feature_importance(list(X_train.columns))
        top_features = feature_importance.head(20).to_dict("records")

        # 记录模型信息
        model_record = ModelRecord(
            model_version=model_version,
            train_date=date.today(),
            data_start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
            data_end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            num_samples=len(X_train),
            num_features=len(X_train.columns),
            params_json=params or {},
            train_ic=train_result.get("valid_ic", 0),
            valid_ic=train_result.get("valid_ic", 0),
            train_rank_ic=train_result.get("valid_rank_ic", 0),
            valid_rank_ic=train_result.get("valid_rank_ic", 0),
            feature_importance_json=top_features,
            model_path=model_path,
            is_active=1,
        )

        # 将旧模型设为非活跃
        self.db.query(ModelRecord).filter(ModelRecord.is_active == 1).update({"is_active": 0})
        self.db.add(model_record)
        self.db.commit()

        return {
            "status": "success",
            "model_version": model_version,
            "model_path": model_path,
            "num_samples": len(X_train),
            "num_features": len(X_train.columns),
            "valid_ic": train_result.get("valid_ic", 0),
            "valid_rank_ic": train_result.get("valid_rank_ic", 0),
            "top_features": top_features[:10],
        }