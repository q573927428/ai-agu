"""LightGBM 模型封装 + 多模型集成"""
import os
import joblib
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from dataclasses import dataclass


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

        from scipy.stats import pearsonr, spearmanr

        # 计算训练集IC
        y_train_pred = self.model.predict(X_train)
        train_ic, _ = pearsonr(y_train_pred, y_train)
        train_rank_ic, _ = spearmanr(y_train_pred, y_train)
        result["train_ic"] = float(train_ic)
        result["train_rank_ic"] = float(train_rank_ic)

        if X_valid is not None and y_valid is not None:
            y_pred = self.model.predict(X_valid)
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


class EnsembleModel:
    """
    多模型集成预测器

    通过加载多个 LightGBM 模型，基于模型间预测一致性计算置信度。
    核心原理：多个模型对同一股票预测结果越一致，置信度越高。
    """

    def __init__(self):
        self.models: List[LightGBMModel] = []
        self.model_versions: List[str] = []
        self.model_ids: List[int] = []
        self.loaded = False

    def add_model(self, model: LightGBMModel, model_version: str, model_id: int = 0):
        """添加一个子模型到集成中"""
        self.models.append(model)
        self.model_versions.append(model_version)
        self.model_ids.append(model_id)
        self.loaded = True
        logger.info(f"集成添加模型: {model_version} (id={model_id})")

    @property
    def count(self) -> int:
        """集成中的模型数量"""
        return len(self.models)

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        多模型集成预测，基于一致性计算置信度

        Args:
            X: 特征 DataFrame

        Returns:
            mean_preds: 平均预测值 (n_samples,) - 最终预测收益率（百分数）
            confidences: 置信度数组 (n_samples,) - 范围 [0, 1]
        """
        if not self.models:
            logger.warning("集成中没有模型，返回零值")
            return np.zeros(len(X)), np.zeros(len(X))

        # 1. 收集每个模型的预测结果
        all_preds = []
        for idx, model in enumerate(self.models):
            try:
                pred = model.predict(X)
                all_preds.append(pred)
                logger.debug(f"模型 {self.model_versions[idx]} 预测完成，均值: {np.mean(pred):.4f}")
            except Exception as e:
                logger.error(f"模型 {self.model_versions[idx]} 预测失败: {e}")
                # 用其他模型的均值填充
                if all_preds:
                    all_preds.append(np.mean(all_preds[-1], keepdims=True) * np.ones(len(X)))
                else:
                    all_preds.append(np.zeros(len(X)))

        # shape: (n_models, n_samples)
        all_preds = np.array(all_preds)

        # 2. 平均预测值作为最终预测
        mean_preds = np.mean(all_preds, axis=0)

        # 3. 计算模型间标准差
        std_preds = np.std(all_preds, axis=0)

        # 4. 基于一致性计算置信度
        confidences = self._compute_consistency_confidence(mean_preds, std_preds, all_preds)

        # 5. 基于极端值惩罚（避免对过高预测过度自信）
        confidences = self._apply_extreme_penalty(mean_preds, confidences)

        # 6. 确保范围 [0, 1]
        confidences = np.clip(confidences, 0, 1)

        logger.info(
            f"集成预测完成: {len(self.models)} 个模型, "
            f"预测均值: {np.mean(mean_preds):.4f}, "
            f"置信度均值: {np.mean(confidences):.4f}"
        )

        return mean_preds, confidences

    def _compute_consistency_confidence(
        self,
        mean_preds: np.ndarray,
        std_preds: np.ndarray,
        all_preds: np.ndarray,
    ) -> np.ndarray:
        """
        基于模型间一致性计算置信度

        核心公式：
        - 变异系数 cv = std / |mean|：衡量相对离散程度
        - 一致性置信度 = 1 / (1 + cv)：cv越小越一致，置信度越高
        - 结合绝对离散度：模型整体标准差小也是信号
        """
        # 防止除零
        abs_mean = np.abs(mean_preds) + 1e-6

        # 变异系数 (CV) — 相对离散度
        cv = std_preds / abs_mean

        # 一致性置信度: CV越小越好
        consistency_conf = 1.0 / (1.0 + cv)

        # 绝对离散度置信度: std越小越好
        # 模型输出是百分数，std=1表示模型间差1%，很一致
        std_conf = np.exp(-std_preds / 3.0)  # std=0->1.0, std=3->0.37, std=10->0.036

        # 模型数量加权：模型越多，一致性越可信
        n_models = len(self.models)
        model_weight = min(n_models / 3.0, 1.0)  # 3个模型以上达到满权重

        # 综合置信度
        confidences = 0.5 * consistency_conf + 0.4 * std_conf + 0.1 * model_weight

        return confidences

    def _apply_extreme_penalty(self, mean_preds: np.ndarray, confidences: np.ndarray) -> np.ndarray:
        """
        对极端预测值施加置信度惩罚

        预测收益率过高（如 > 30%）通常是过拟合信号，应降低置信度
        """
        # 对预测值绝对值过大的情况打折扣
        abs_pred = np.abs(mean_preds)
        penalty = np.ones_like(abs_pred)

        # 预测值超过 20% 开始惩罚
        extreme_mask = abs_pred > 20
        penalty[extreme_mask] = np.exp(-(abs_pred[extreme_mask] - 20) / 20)
        penalty[extreme_mask] = np.clip(penalty[extreme_mask], 0.3, 1.0)

        return confidences * penalty

    def get_model_divergence(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        获取各模型间的分歧度分析（用于调试）
        """
        if not self.models:
            return pd.DataFrame()

        all_preds = []
        for model in self.models:
            all_preds.append(model.predict(X))
        all_preds = np.array(all_preds)

        divergence = {
            "mean": np.mean(all_preds, axis=0),
            "std": np.std(all_preds, axis=0),
            "min": np.min(all_preds, axis=0),
            "max": np.max(all_preds, axis=0),
            "range": np.max(all_preds, axis=0) - np.min(all_preds, axis=0),
        }

        for i, ver in enumerate(self.model_versions):
            divergence[f"pred_{ver}"] = all_preds[i]

        return pd.DataFrame(divergence)