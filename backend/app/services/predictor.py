"""预测器 - 每日预测全市场股票（多模型集成版）"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, List
from loguru import logger
from sqlalchemy.orm import Session
from app.ml.model import LightGBMModel, EnsembleModel
from app.models.factor import FactorStore
from app.models.prediction import Prediction
from app.models.model_record import ModelRecord
from app.models.stock import StockBasic
from app.config import settings
from app.utils.date_utils import get_next_trade_day


PREDICTION_MIN_STD_PCT = 1.0
PREDICTION_TARGET_STD_PCT = 3.0
PREDICTION_LIMIT_BUFFER = 0.98


class Predictor:
    """预测器（多模型集成）"""

    def __init__(self, db: Session):
        self.db = db
        self.ensemble = EnsembleModel()

    def _load_active_models(self, max_models: int = 5):
        """加载最近训练的次日预测模型用于集成预测"""
        records = (
            self.db.query(ModelRecord)
            .filter(
                ModelRecord.model_path.isnot(None),
                ModelRecord.is_active == 1,
            )
            .order_by(ModelRecord.id.desc())
            .limit(max_models)
            .all()
        )

        if not records:
            logger.warning("没有活跃模型（次日预测）")
            return False

        self.ensemble = EnsembleModel()
        loaded_count = 0
        for record in records:
            if not record.model_path or not os.path.exists(record.model_path):
                logger.warning(f"模型文件不存在: {record.model_path}")
                continue
            model = LightGBMModel(record.model_path)
            self.ensemble.add_model(model, record.model_version, record.id)
            loaded_count += 1

        if loaded_count == 0:
            logger.error("没有成功加载任何次日预测模型")
            return False

        logger.info(f"次日集成模型加载完成: {loaded_count} 个模型")
        return True

    def _get_price_limit_pct_map(self, stock_codes: List[str]) -> dict:
        """按A股交易规则估算不同股票的单日涨跌停幅度（百分数口径）。"""
        if not stock_codes:
            return {}

        basics = (
            self.db.query(
                StockBasic.stock_code,
                StockBasic.stock_name,
                StockBasic.market,
                StockBasic.exchange,
            )
            .filter(StockBasic.stock_code.in_(stock_codes))
            .all()
        )

        basic_map = {row.stock_code: row for row in basics}
        limit_map = {}
        for code in stock_codes:
            row = basic_map.get(code)
            name = (row.stock_name or "") if row else ""
            market = (row.market or "") if row else ""
            exchange = (row.exchange or "") if row else ""

            if "ST" in name.upper() or "*ST" in name.upper():
                limit = 5.0
            elif exchange == "BSE" or code.startswith(("4", "8")):
                limit = 30.0
            elif "科创" in market or code.startswith(("688", "689")):
                limit = 20.0
            elif "创业" in market or code.startswith(("300", "301")):
                limit = 20.0
            else:
                limit = 10.0

            limit_map[code] = limit * PREDICTION_LIMIT_BUFFER

        return limit_map

    def _calibrate_prediction_distribution(self, preds: np.ndarray, stock_codes: List[str]) -> np.ndarray:
        """横截面校准预测分布，避免RMSE回归输出全部挤在均值附近。

        LightGBM 回归次日收益时常会输出很窄的区间，排序仍有价值，但收益率数值不直观。
        当全市场预测标准差过小时，将横截面 z-score 拉伸到目标波动，并按A股涨跌停规则限制极端值。
        输入/输出均为百分数口径，如 5.0 表示 5%。
        """
        preds = np.asarray(preds, dtype=float)
        if len(preds) < 2:
            return preds

        limit_map = self._get_price_limit_pct_map(stock_codes)
        limits = np.array([limit_map.get(code, 9.8) for code in stock_codes], dtype=float)

        mean = float(np.nanmean(preds))
        std = float(np.nanstd(preds))
        if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
            preds = np.nan_to_num(preds, nan=0.0, posinf=0.0, neginf=0.0)
            return np.clip(preds, -limits, limits)

        if std >= PREDICTION_MIN_STD_PCT:
            return np.clip(preds, -limits, limits)

        z_scores = (preds - mean) / std
        calibrated = mean + z_scores * PREDICTION_TARGET_STD_PCT
        calibrated = np.clip(calibrated, -limits, limits)
        logger.info(
            f"预测分布校准: 原始均值={mean:.4f}%, 原始std={std:.4f}%, "
            f"校准std目标={PREDICTION_TARGET_STD_PCT:.2f}%, 已按个股涨跌停约束"
        )
        return calibrated

    def predict_daily(self, trade_date: str) -> pd.DataFrame:
        """每日预测全市场股票（多模型集成版）"""
        trade_date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()

        # 加载次日集成模型
        if not self._load_active_models():
            logger.error("无法加载次日预测模型，跳过预测")
            return pd.DataFrame()

        # 获取当日因子数据
        factors = (
            self.db.query(FactorStore)
            .filter(FactorStore.trade_date == trade_date_obj)
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

        # 集成预测
        mean_preds, confidences = self.ensemble.predict(X)
        mean_preds = self._calibrate_prediction_distribution(mean_preds, stock_codes)

        # 模型版本号
        model_versions = self.ensemble.model_versions
        short_versions = [v[-7:] for v in model_versions]
        model_version = "+".join(short_versions[:3]) if short_versions else "ensemble"
        if len(short_versions) > 3:
            model_version += f"+{len(short_versions) - 3}more"

        # 保存预测结果
        predict_date = date.today()
        target_date = get_next_trade_day(datetime.combine(trade_date_obj, datetime.min.time())).date()

        # 删除旧预测
        self.db.query(Prediction).filter(Prediction.predict_date == predict_date).delete()

        results = []
        for i, stock_code in enumerate(stock_codes):
            pred = float(mean_preds[i]) / 100.0  # 百分数转小数
            conf = float(confidences[i])

            prediction = Prediction(
                stock_code=stock_code,
                predict_date=predict_date,
                target_date=target_date,
                predicted_return=round(pred, 6),
                confidence=round(conf, 4),
                model_version=model_version,
                rank_score=pred,
            )
            self.db.add(prediction)
            results.append({
                "stock_code": stock_code,
                "predicted_return": pred,
                "confidence": conf,
            })

        self.db.commit()

        # 按预测收益率排序
        results.sort(key=lambda x: x["predicted_return"], reverse=True)

        df = pd.DataFrame(results)
        logger.info(
            f"集成预测完成: {len(results)} 只股票, "
            f"集成模型数: {self.ensemble.count}, "
            f"模型版本: {model_version}"
        )
        return df

    def get_top_n(self, predict_date: str, n: int = 50) -> List[dict]:
        """获取当日预测收益率最高的N只股票"""
        predict_date_obj = datetime.strptime(predict_date, "%Y-%m-%d").date() if isinstance(predict_date, str) else predict_date
        predictions = (
            self.db.query(Prediction)
            .filter(Prediction.predict_date == predict_date_obj)
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
