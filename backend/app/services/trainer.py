"""LightGBM训练器（多模型集成版）"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session
from app.ml.model import LightGBMModel
from app.models.factor import FactorStore
from app.models.model_record import ModelRecord
from app.models.stock_daily import StockDaily
from app.config import settings


# 单日收益率噪声和极端涨跌停会显著放大回归模型过拟合，训练前先做温和去极值。
LABEL_CLIP_QUANTILE = 0.01
MIN_TRAIN_DATES = 20


# ============ 多模型集成训练的异构超参数配置（次日预测） ============
ENSEMBLE_PARAMS: List[Dict[str, Any]] = [
    {
        # 模型A: 稳健主模型，降低叶子数并加强L2，适合高噪声次日收益预测
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 23,
        "max_depth": 6,
        "learning_rate": 0.035,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 80,
        "min_split_gain": 0.01,
        "reg_alpha": 0.3,
        "reg_lambda": 2.0,
        "verbose": -1,
        "random_state": 42,
    },
    {
        # 模型B: 浅树强正则，偏低方差
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 19,
        "max_depth": 5,
        "learning_rate": 0.04,
        "feature_fraction": 0.78,
        "bagging_fraction": 0.78,
        "bagging_freq": 3,
        "min_child_samples": 70,
        "min_split_gain": 0.01,
        "reg_alpha": 0.3,
        "reg_lambda": 2.0,
        "verbose": -1,
        "random_state": 100,
    },
    {
        # 模型C: extra_trees 增加随机切分，保留早停能力并提升集成多样性
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "max_depth": 7,
        "learning_rate": 0.03,
        "feature_fraction": 0.65,
        "bagging_fraction": 0.7,
        "bagging_freq": 5,
        "min_child_samples": 100,
        "extra_trees": True,
        "min_split_gain": 0.01,
        "reg_alpha": 0.8,
        "reg_lambda": 4.0,
        "verbose": -1,
        "random_state": 7,
    },
    {
        # 模型D: GOSS采样关注梯度较大的样本，替代RMSE偏弱的RF子模型
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "goss",
        "num_leaves": 23,
        "max_depth": 6,
        "learning_rate": 0.035,
        "feature_fraction": 0.75,
        "top_rate": 0.2,
        "other_rate": 0.1,
        "min_child_samples": 80,
        "min_split_gain": 0.01,
        "reg_alpha": 0.5,
        "reg_lambda": 2.5,
        "verbose": -1,
        "random_state": 2024,
    },
    {
        # 模型E: 保守强正则，更多特征/样本随机性
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 23,
        "max_depth": 5,
        "learning_rate": 0.035,
        "feature_fraction": 0.68,
        "bagging_fraction": 0.72,
        "bagging_freq": 4,
        "min_child_samples": 90,
        "min_split_gain": 0.01,
        "reg_alpha": 0.8,
        "reg_lambda": 3.5,
        "verbose": -1,
        "random_state": 888,
    },
]


class Trainer:
    """训练器 - 同时训练多个异构模型用于集成"""

    def __init__(self, db: Session):
        self.db = db

    def _sanitize_features(self, df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """训练前特征清洗：处理NaN/Inf，并按列做温和去极值，降低异常因子影响。"""
        X = df[feature_cols].copy()
        X = X.replace([np.inf, -np.inf], np.nan)

        for col in feature_cols:
            median = X[col].median()
            X[col] = X[col].fillna(0.0 if pd.isna(median) else median)

            lower = X[col].quantile(0.01)
            upper = X[col].quantile(0.99)
            if np.isfinite(lower) and np.isfinite(upper) and lower < upper:
                X[col] = X[col].clip(lower, upper)

        return X.astype(float)

    def _clip_labels(self, y: pd.Series) -> pd.Series:
        """对次日收益率标签做分位数去极值，避免极端涨跌幅主导RMSE优化。"""
        y = y.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
        if y.empty:
            return y

        lower = y.quantile(LABEL_CLIP_QUANTILE)
        upper = y.quantile(1 - LABEL_CLIP_QUANTILE)
        if np.isfinite(lower) and np.isfinite(upper) and lower < upper:
            clipped = y.clip(lower, upper)
            logger.info(f"标签去极值: [{lower:.4f}, {upper:.4f}], 原始样本 {len(y)} 条")
            return clipped
        return y

    def prepare_training_data(self, start_date: str, end_date: str) -> tuple:
        """准备训练数据（分批加载 + 预计算标签，避免内存溢出和慢查询）"""
        # 先获取范围内的所有交易日
        date_rows = (
            self.db.query(FactorStore.trade_date)
            .filter(FactorStore.trade_date.between(start_date, end_date))
            .distinct()
            .order_by(FactorStore.trade_date)
            .all()
        )
        all_dates = [r[0] for r in date_rows]
        if not all_dates:
            logger.warning(f"在 {start_date} ~ {end_date} 范围内没有因子数据")
            return None, None, None, None

        # 特征列名（缓存，仅需获取一次）
        factor_col_names = [
            col.name for col in FactorStore.__table__.columns
            if col.name not in ("id", "stock_code", "trade_date", "created_at")
        ]

        # ====== 一次性预计算所有标签 ======
        logger.info("预计算次日收益率标签...")
        label_map = self._precompute_labels(all_dates[0], end_date)
        logger.info(f"预计算完成，共 {len(label_map)} 条有效标签")

        # 分批处理，每批 100 个交易日
        BATCH_SIZE = 100
        dfs = []
        total_batches = (len(all_dates) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, len(all_dates), BATCH_SIZE):
            batch_dates = all_dates[i:i + BATCH_SIZE]
            batch_start = str(batch_dates[0])
            batch_end = str(batch_dates[-1])

            factors = (
                self.db.query(FactorStore)
                .filter(FactorStore.trade_date.between(batch_start, batch_end))
                .all()
            )

            # 构建当前批次的记录列表
            records = []
            for f in factors:
                record = {
                    "stock_code": f.stock_code,
                    "trade_date": f.trade_date,
                }
                for col_name in factor_col_names:
                    val = getattr(f, col_name)
                    try:
                        num_val = float(val) if val is not None else 0.0
                    except (TypeError, ValueError):
                        num_val = 0.0
                    record[col_name] = num_val if np.isfinite(num_val) else 0.0
                records.append(record)

            if not records:
                continue

            batch_df = pd.DataFrame(records)

            # 使用预计算标签映射
            batch_df["future_return_1d"] = batch_df.apply(
                lambda row: label_map.get((row["stock_code"], row["trade_date"])),
                axis=1,
            )
            batch_df = batch_df.dropna(subset=["future_return_1d"])
            if not batch_df.empty:
                dfs.append(batch_df)

            logger.debug(f"处理批次 {i // BATCH_SIZE + 1}/{total_batches}: "
                         f"{batch_start} ~ {batch_end}, "
                         f"当前批次 {len(batch_df)} 条有效数据")

        if not dfs:
            logger.warning("所有批次处理后均无有效数据")
            return None, None, None, None

        df = pd.concat(dfs, ignore_index=True)

        if df.empty:
            return None, None, None, None

        # 特征列（排除非因子列）
        feature_cols = [c for c in df.columns if c not in ("stock_code", "trade_date", "future_return_1d")]

        X = self._sanitize_features(df, feature_cols)
        y = self._clip_labels(df["future_return_1d"])
        df = df.loc[y.index]
        X = X.loc[y.index]

        # 按时间分割
        unique_dates = sorted(df["trade_date"].unique())
        if len(unique_dates) < 3:
            logger.warning(f"有效交易日过少，无法进行时间序列验证: {len(unique_dates)} 天")
            return None, None, None, None

        split_idx = int(len(unique_dates) * 0.75)
        split_idx = min(max(split_idx, 1), len(unique_dates) - 1)
        if split_idx < MIN_TRAIN_DATES and len(unique_dates) > MIN_TRAIN_DATES:
            split_idx = MIN_TRAIN_DATES
        train_dates = unique_dates[:split_idx]

        train_mask = df["trade_date"].isin(train_dates)
        X_train = X[train_mask]
        y_train = y[train_mask]
        X_valid = X[~train_mask]
        y_valid = y[~train_mask]

        if X_train.empty or X_valid.empty:
            logger.warning(f"训练/验证数据为空: train={len(X_train)}, valid={len(X_valid)}")
            return None, None, None, None

        logger.info(f"训练数据: {len(X_train)} 条, 验证数据: {len(X_valid)} 条, 特征: {len(feature_cols)} 个")
        return X_train, y_train, X_valid, y_valid

    def _precompute_labels(self, start_date, end_date) -> dict:
        """分批预计算所有 (stock_code, trade_date) → future_return_1d 标签（次日收益率）"""
        # 获取所有股票列表
        stock_rows = (
            self.db.query(StockDaily.stock_code)
            .filter(StockDaily.trade_date.between(start_date, end_date))
            .distinct()
            .all()
        )
        stock_codes = [r[0] for r in stock_rows]
        logger.info(f"共 {len(stock_codes)} 只股票需要计算标签")

        # 分批处理每只股票，避免 IN 查询过慢
        LABEL_BATCH = 200  # 每批 200 只股票
        label_map = {}

        for i in range(0, len(stock_codes), LABEL_BATCH):
            batch_codes = stock_codes[i:i + LABEL_BATCH]

            rows = (
                self.db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.pct_chg)
                .filter(
                    StockDaily.stock_code.in_(batch_codes),
                    StockDaily.trade_date.between(start_date, end_date),
                )
                .order_by(StockDaily.stock_code, StockDaily.trade_date)
                .all()
            )

            rows_by_stock = {}
            for stock_code, trade_date, pct_chg in rows:
                rows_by_stock.setdefault(stock_code, []).append((trade_date, pct_chg))

            for stock_code, stock_rows in rows_by_stock.items():
                stock_rows.sort(key=lambda item: item[0])
                for idx in range(len(stock_rows) - 1):
                    current_date, _ = stock_rows[idx]
                    _, next_pct_chg = stock_rows[idx + 1]
                    if next_pct_chg is None:
                        continue
                    # 下一交易日收益率 = 同一股票下一条交易记录的 pct_chg。
                    # pct_chg 已存为百分数（如 5.0 = 5%），训练标签也保持百分数口径。
                    label_map[(stock_code, current_date)] = float(next_pct_chg)

            logger.info(f"标签计算进度: {min(i + LABEL_BATCH, len(stock_codes))}/{len(stock_codes)} 只股票")

        return label_map

    def _train_single_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame,
        y_valid: pd.Series,
        params: Dict[str, Any],
        model_tag: str,
    ) -> Dict[str, Any]:
        """训练单个子模型"""
        model = LightGBMModel()
        train_result = model.train(X_train, y_train, X_valid, y_valid, params)

        # 生成版本号
        now = datetime.now()
        model_version = f"{model_tag}_v{now.strftime('%Y%m%d_%H%M%S')}"
        model_path = os.path.join(settings.model_dir, f"ensemble_{model_version}.txt")
        os.makedirs(settings.model_dir, exist_ok=True)
        model.save_model(model_path)

        # 特征重要性
        feature_importance = model.get_feature_importance(list(X_train.columns))
        top_features = feature_importance.head(20).to_dict("records")

        return {
            "model": model,
            "model_version": model_version,
            "model_path": model_path,
            "num_samples": len(X_train),
            "num_features": len(X_train.columns),
            "train_ic": train_result.get("train_ic", 0),
            "train_rank_ic": train_result.get("train_rank_ic", 0),
            "valid_ic": train_result.get("valid_ic", 0),
            "valid_rank_ic": train_result.get("valid_rank_ic", 0),
            "params": params,
            "top_features": top_features[:10],
        }

    def train(
        self,
        start_date: str,
        end_date: str,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        训练多模型集成（默认训练5个异构模型）

        Args:
            start_date: 训练数据起始日期
            end_date: 训练数据截止日期
            params: 如果提供，仅训练单个模型（兼容旧调用）

        Returns:
            训练结果
        """
        result = self.prepare_training_data(start_date, end_date)
        if result[0] is None:
            return {"status": "failed", "message": "训练数据不足"}

        X_train, y_train, X_valid, y_valid = result

        # ====== 如果传入了 params，兼容旧调用：只训练一个模型 ======
        if params is not None:
            model = LightGBMModel()
            train_result = model.train(X_train, y_train, X_valid, y_valid, params)
            model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = os.path.join(settings.model_dir, f"model_{model_version}.txt")
            os.makedirs(settings.model_dir, exist_ok=True)
            model.save_model(model_path)

            feature_importance = model.get_feature_importance(list(X_train.columns))
            top_features = feature_importance.head(20).to_dict("records")

            # 将旧模型设为非活跃
            self.db.query(ModelRecord).filter(
                ModelRecord.is_active == 1,
            ).update({"is_active": 0})

            model_record = ModelRecord(
                model_version=model_version,
                train_date=date.today(),
                data_start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                data_end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
                num_samples=len(X_train),
                num_features=len(X_train.columns),
                params_json=params or {},
                train_ic=train_result.get("train_ic", 0),
                valid_ic=train_result.get("valid_ic", 0),
                train_rank_ic=train_result.get("train_rank_ic", 0),
                valid_rank_ic=train_result.get("valid_rank_ic", 0),
                feature_importance_json=top_features,
                model_path=model_path,
                is_active=1,
            )
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
                "note": "single model (legacy mode)",
            }

        # ====== 默认：训练多个异构模型用于集成 ======
        model_results = []
        for idx, model_params in enumerate(ENSEMBLE_PARAMS):
            model_tag = f"model{chr(65 + idx)}"  # A, B, C, D, E
            try:
                logger.info(f"训练集成子模型 {model_tag} ({idx + 1}/{len(ENSEMBLE_PARAMS)})...")
                m_result = self._train_single_model(
                    X_train, y_train, X_valid, y_valid, model_params, model_tag
                )
                model_results.append(m_result)
                logger.info(f"模型 {model_tag} 训练完成, IC={m_result['valid_ic']:.4f}")
            except Exception as e:
                logger.error(f"模型 {model_tag} 训练失败: {e}")
                continue

        if not model_results:
            return {"status": "failed", "message": "所有模型训练失败"}

        # 将旧模型设为非活跃
        self.db.query(ModelRecord).filter(
            ModelRecord.is_active == 1,
        ).update({"is_active": 0})

        # 保存所有模型到数据库
        saved_records = []
        for m_res in model_results:
            record = ModelRecord(
                model_version=m_res["model_version"],
                train_date=date.today(),
                data_start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                data_end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
                num_samples=m_res["num_samples"],
                num_features=m_res["num_features"],
                params_json=m_res["params"],
                train_ic=m_res["train_ic"],
                valid_ic=m_res["valid_ic"],
                train_rank_ic=m_res["train_rank_ic"],
                valid_rank_ic=m_res["valid_rank_ic"],
                feature_importance_json=m_res["top_features"],
                model_path=m_res["model_path"],
                is_active=1,
            )
            self.db.add(record)
            self.db.flush()
            saved_records.append({**m_res, "db_id": record.id})

        self.db.commit()

        # 计算集成指标：各模型的 IC 统计
        ics = [m["valid_ic"] for m in model_results]

        logger.info(
            f"多模型集成训练完成: {len(model_results)} 个子模型, "
            f"IC均值: {np.mean(ics):.4f}, "
            f"IC标准差: {np.std(ics):.4f}"
        )

        return {
            "status": "success",
            "ensemble_size": len(model_results),
            "model_versions": [m["model_version"] for m in model_results],
            "model_paths": [m["model_path"] for m in model_results],
            "valid_ic_mean": float(np.mean(ics)),
            "valid_ic_std": float(np.std(ics)),
            "note": "multi-model ensemble",
        }







