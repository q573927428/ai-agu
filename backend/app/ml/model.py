"""LightGBM 模型封装"""
import os
import joblib
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from loguru import logger


class LightGBMModel:
    """LightGBM 模型封装类"""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, X_valid: Optional[pd.DataFrame] = None,
              y_valid: Optional[pd.Series] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """训练模型"""
        try:
            import lightgbm as lgb
        except ImportError:
            logger.error("lightgbm 未安装，使用模拟模式")
            return {"status": "simulated", "message": "lightgbm not installed"}

        if params is None:
            params = {
                "objective": "regression",
                "metric": "rmse",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "max_depth": 7,
                "learning_rate": 0.05,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "min_child_samples": 20,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "verbose": -1,
                "random_state": 42,
            }

        train_data = lgb.Dataset(X_train, label=y_train)
        valid_sets = [train_data]
        valid_names = ["train"]

        if X_valid is not None and y_valid is not None:
            valid_data = lgb.Dataset(X_valid, label=y_valid, reference=train_data)
            valid_sets.append(valid_data)
            valid_names.append("valid")

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
        )

        # 计算训练指标
        result = {"status": "trained", "num_boost_round": self.model.best_iteration}
        if X_valid is not None and y_valid is not None:
            y_pred = self.model.predict(X_valid)
            from scipy.stats import pearsonr, spearmanr
            ic, _ = pearsonr(y_pred, y_valid)
            rank_ic, _ = spearmanr(y_pred, y_valid)
            result["valid_ic"] = float(ic)
            result["valid_rank_ic"] = float(rank_ic)

        return result

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测"""
        if self.model is None:
            logger.warning("模型未加载，返回随机值")
            return np.random.randn(len(X)) * 0.01
        return self.model.predict(X)

    def save_model(self, path: str):
        """保存模型"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self.model is not None:
            self.model.save_model(path)
        else:
            joblib.dump(self.model, path)
        self.model_path = path
        logger.info(f"模型已保存: {path}")

    def load_model(self, path: str):
        """加载模型"""
        try:
            import lightgbm as lgb
            self.model = lgb.Booster(model_file=path)
            self.model_path = path
            logger.info(f"模型已加载: {path}")
        except Exception as e:
            logger.error(f"加载模型失败: {e}")

    def get_feature_importance(self, feature_names: list) -> pd.DataFrame:
        """获取特征重要性"""
        if self.model is None:
            return pd.DataFrame({"feature": feature_names, "importance": [0] * len(feature_names)})

        importance = self.model.feature_importance(importance_type="gain")
        df = pd.DataFrame({"feature": feature_names, "importance": importance})
        df = df.sort_values("importance", ascending=False).reset_index(drop=True)
        df["rank"] = range(1, len(df) + 1)
        return df