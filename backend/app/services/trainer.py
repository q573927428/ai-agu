"""LightGBM训练器（多模型集成版）"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session
from sklearn.model_selection import train_test_split
from app.ml.model import LightGBMModel
from app.models.factor import FactorStore
from app.models.model_record import ModelRecord
from app.models.stock_daily import StockDaily
from app.config import settings


# ============ 多模型集成训练的异构超参数配置 ============
# 不同模型的超参数不同，使其从不同角度学习，提高集成多样性
ENSEMBLE_PARAMS: List[Dict[str, Any]] = [
    {
        # 模型A: 默认主模型
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
    },
    {
        # 模型B: 更浅的树 + 更高学习率（更快适应，但防止过拟合）
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 15,
        "max_depth": 5,
        "learning_rate": 0.08,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.7,
        "bagging_freq": 3,
        "min_child_samples": 30,
        "reg_alpha": 0.2,
        "reg_lambda": 0.3,
        "verbose": -1,
        "random_state": 100,
    },
    {
        # 模型C: 更深 + dropout-like 正则（更复杂，但也更谨慎）
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 63,
        "max_depth": 10,
        "learning_rate": 0.03,
        "feature_fraction": 0.6,
        "bagging_fraction": 0.6,
        "bagging_freq": 7,
        "min_child_samples": 10,
        "reg_alpha": 0.5,
        "reg_lambda": 0.5,
        "verbose": -1,
        "random_state": 7,
    },
    {
        # 模型D: 随机森林模式（对异常值更鲁棒）
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "rf",
        "num_leaves": 31,
        "max_depth": 7,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "min_child_samples": 20,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "random_state": 2024,
    },
    {
        # 模型E: 更保守的梯度提升（更低的特征采样，更强的L2）
        "objective": "regression",
        "metric": "rmse",
        "boosting_type": "gbdt",
        "num_leaves": 23,
        "max_depth": 6,
        "learning_rate": 0.04,
        "feature_fraction": 0.5,
        "bagging_fraction": 0.75,
        "bagging_freq": 4,
        "min_child_samples": 25,
        "reg_alpha": 1.0,
        "reg_lambda": 2.0,
        "verbose": -1,
        "random_state": 888,
    },
]


class Trainer:
    """训练器 - 同时训练多个异构模型用于集成"""

    def __init__(self, db: Session):
        self.db = db

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
        logger.info("预计算未来20日收益率标签...")
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
                    record[col_name] = float(val) if val is not None else 0.0
                records.append(record)

            if not records:
                continue

            batch_df = pd.DataFrame(records)

            # 使用预计算标签映射
            batch_df["future_return_20d"] = batch_df.apply(
                lambda row: label_map.get((row["stock_code"], row["trade_date"])),
                axis=1,
            )
            batch_df = batch_df.dropna(subset=["future_return_20d"])
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

    def _precompute_labels(self, start_date, end_date) -> dict:
        """分批预计算所有 (stock_code, trade_date) → future_return_20d 标签"""
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
                self.db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.close)
                .filter(
                    StockDaily.stock_code.in_(batch_codes),
                    StockDaily.trade_date.between(start_date, end_date),
                )
                .order_by(StockDaily.stock_code, StockDaily.trade_date)
                .all()
            )

            current_stock = None
            dates_list = []
            close_list = []

            for row in rows:
                sc, td, close = row
                if close is None:
                    continue
                close_val = float(close)

                if sc != current_stock:
                    if current_stock and len(dates_list) >= 21:
                        for idx in range(len(dates_list) - 20):
                            future_return = (close_list[idx + 20] / close_list[idx] - 1) * 100
                            label_map[(current_stock, dates_list[idx])] = future_return
                    current_stock = sc
                    dates_list = [td]
                    close_list = [close_val]
                else:
                    dates_list.append(td)
                    close_list.append(close_val)

            # 处理当前批次最后一只股票
            if current_stock and len(dates_list) >= 21:
                for idx in range(len(dates_list) - 20):
                    future_return = (close_list[idx + 20] / close_list[idx] - 1) * 100
                    label_map[(current_stock, dates_list[idx])] = future_return

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
            self.db.query(ModelRecord).filter(ModelRecord.is_active == 1).update({"is_active": 0})

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
        self.db.query(ModelRecord).filter(ModelRecord.is_active == 1).update({"is_active": 0})

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
                train_ic=m_res["valid_ic"],
                valid_ic=m_res["valid_ic"],
                train_rank_ic=m_res["valid_rank_ic"],
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
