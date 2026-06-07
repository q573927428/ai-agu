"""预测器 - 每日预测全市场股票"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional, List
from loguru import logger
from sqlalchemy.orm import Session
from app.ml.model import LightGBMModel
from app.models.factor import FactorStore
from app.models.prediction import Prediction
from app.models.model_record import ModelRecord
from app.config import settings


class Predictor:
    """预测器"""

    def __init__(self, db: Session):
        self.db = db
        self.model = None

    def _load_active_model(self):
        """加载当前活跃模型"""
        record = (
            self.db.query(ModelRecord)
            .filter(ModelRecord.is_active == 1)
            .order_by(ModelRecord.id.desc())
            .first()
        )

        if not record or not record.model_path:
            logger.warning("没有活跃模型")
            return False

        if not os.path.exists(record.model_path):
            logger.warning(f"模型文件不存在: {record.model_path}")
            return False

        self.model = LightGBMModel(record.model_path)
        return True

    def predict_daily(self, trade_date: str) -> pd.DataFrame:
        """每日预测全市场股票"""
        # 加载模型
        if not self._load_active_model():
            logger.error("无法加载模型，跳过预测")
            return pd.DataFrame()

        # 获取当日因子数据
        factors = (
            self.db.query(FactorStore)
            .filter(FactorStore.trade_date == trade_date)
            .all()
        )

        if not factors:
            logger.warning(f"{trade_date} 没有因子数据")
            return pd.DataFrame()

        # 构建特征数据
        records = []
        stock_codes = []
        for f in factors:
            record = {}
            for col in FactorStore.__table__.columns:
                if col.name in ("id", "stock_code", "trade_date", "created_at"):
                    continue
                val = getattr(f, col.name)
                record[col.name] = float(val) if val is not None else 0.0
            records.append(record)
            stock_codes.append(f.stock_code)

        X = pd.DataFrame(records)

        # 预测
        predictions = self.model.predict(X)

        # 模型版本
        model_version = (
            self.db.query(ModelRecord)
            .filter(ModelRecord.is_active == 1)
            .value(ModelRecord.model_version)
        ) or "unknown"

        # 保存预测结果
        predict_date = date.today()
        target_date = datetime.strptime(trade_date, "%Y-%m-%d").date() + timedelta(days=20)

        # 删除旧预测
        self.db.query(Prediction).filter(Prediction.predict_date == predict_date).delete()

        results = []
        for i, (stock_code, pred) in enumerate(zip(stock_codes, predictions)):
            # 置信度基于模型原始输出(百分数)计算，典型范围0~30，归一化到0-1
            raw_pred = float(pred)
            confidence = min(max(float(np.abs(raw_pred)) / 30, 0), 1)

            # 模型预测值为百分数（如5.2表示5.2%），存储为小数（0.052）
            pred_decimal = raw_pred / 100.0

            prediction = Prediction(
                stock_code=stock_code,
                predict_date=predict_date,
                target_date=target_date,
                predicted_return=round(pred_decimal, 6),
                confidence=round(confidence, 4),
                model_version=model_version,
                rank_score=pred_decimal,
            )
            self.db.add(prediction)
            results.append({
                "stock_code": stock_code,
                "predicted_return": pred_decimal,
                "confidence": confidence,
            })

        self.db.commit()

        # 按预测收益率排序
        results.sort(key=lambda x: x["predicted_return"], reverse=True)

        df = pd.DataFrame(results)
        logger.info(f"预测完成: {len(results)} 只股票, 模型版本: {model_version}")
        return df

    def get_top_n(self, predict_date: str, n: int = 50) -> List[dict]:
        """获取当日预测收益率最高的N只股票"""
        predictions = (
            self.db.query(Prediction)
            .filter(Prediction.predict_date == predict_date)
            .order_by(Prediction.predicted_return.desc())
            .limit(n)
            .all()
        )

        results = []
        for i, p in enumerate(predictions, 1):
            results.append({
                "rank": i,
                "stock_code": p.stock_code,
                "predicted_return": float(p.predicted_return or 0),
                "confidence": float(p.confidence or 0),
            })

        return results