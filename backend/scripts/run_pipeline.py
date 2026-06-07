"""一键运行完整流水线"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date, timedelta
from loguru import logger
import pandas as pd
from sqlalchemy.orm import Session
from app.utils.db_utils import SessionLocal
from app.services.factor_engine import FactorEngine
from app.services.label_generator import LabelGenerator
from app.services.predictor import Predictor
from app.services.ranking_service import RankingService
from app.services.trainer import Trainer


def _check_and_train_model(db: Session, trade_date: str) -> bool:
    """检查是否有活跃模型，如果没有则尝试训练

    Returns:
        bool: 模型是否就绪
    """
    from app.models.model_record import ModelRecord
    from app.models.stock_daily import StockDaily

    has_model = db.query(ModelRecord).filter(ModelRecord.is_active == 1).first()
    if has_model:
        return True

    logger.warning("⚠️ 没有活跃模型，尝试训练...")

    # 获取已有历史交易日，用于批量计算因子
    trade_dates = [
        r[0] for r in db.query(StockDaily.trade_date)
        .distinct()
        .order_by(StockDaily.trade_date.asc())
        .all()
    ]

    if len(trade_dates) < 25:
        logger.warning(f"历史交易日不足(只有{len(trade_dates)}天)，无法训练")
        return False

    # 取前80%作为训练用日期
    train_dates = [str(d) for d in trade_dates[:int(len(trade_dates) * 0.8)]]
    if len(train_dates) < 10:
        logger.warning("有效训练日期不足")
        return False

    logger.info(f"批量计算 {len(train_dates)} 个交易日的历史因子...")

    engine = FactorEngine(db)
    factor_count = 0
    # 倒序遍历，保留最新的因子数据
    for dt in reversed(train_dates):
        df = engine.compute_all(dt)
        if not df.empty:
            engine.save_factors(df)
            factor_count += len(df)

    logger.info(f"历史因子计算完成: {factor_count} 条")

    # 检查因子表是否有数据
    from app.models.factor import FactorStore
    total_factors = db.query(FactorStore).count()
    if total_factors == 0:
        logger.warning("因子表中无数据，无法训练")
        return False

    logger.info(f"因子表总计: {total_factors} 条")

    # 训练模型
    train_start = train_dates[0]
    train_end = train_dates[-1]
    trainer = Trainer(db)
    result = trainer.train(start_date=train_start, end_date=train_end)

    if result.get("status") == "success":
        if result.get("note") == "multi-model ensemble":
            logger.info(
                f"✅ 多模型集成训练成功: "
                f"{result['ensemble_size']} 个子模型, "
                f"IC均值={result['valid_ic_mean']:.4f}"
            )
        else:
            logger.info(f"✅ 模型训练成功: {result['model_version']}, IC={result['valid_ic']:.4f}")
        return True
    else:
        logger.warning(f"⚠️ 模型训练失败: {result.get('message', '未知错误')}")
        return False


def run_pipeline(trade_date: str = None, top_n: int = 0):
    """运行完整流水线

    Args:
        trade_date: 交易日期
        top_n: 限制处理的股票数量，0=全部
    """
    if trade_date is None:
        trade_date = date.today().strftime("%Y-%m-%d")

    logger.info(f"=== 开始运行流水线: {trade_date} ===")
    if top_n > 0:
        logger.info(f"⚠️ 限制模式: 仅处理前 {top_n} 只股票")

    db = SessionLocal()
    try:
        # Step 1: 因子计算
        logger.info("[1/4] 计算因子...")
        engine = FactorEngine(db)
        df = engine.compute_all(trade_date, top_n=top_n)
        if not df.empty:
            engine.save_factors(df)
        logger.info(f"✅ 因子计算完成: {len(df)} 只股票")

        # Step 2: 标签生成
        logger.info("[2/4] 生成标签...")
        label_gen = LabelGenerator(db)
        labels = label_gen.generate_labels(trade_date)
        logger.info(f"✅ 标签生成完成: {len(labels)} 条")

        # Step 2.5: 检查/训练模型
        model_ready = _check_and_train_model(db, trade_date)

        # Step 3: 预测
        logger.info("[3/4] 预测...")
        predictor = Predictor(db)
        if model_ready:
            predictions = predictor.predict_daily(trade_date)
        else:
            logger.warning("模型未就绪，跳过预测")
            predictions = pd.DataFrame()
        logger.info(f"✅ 预测完成: {len(predictions)} 只股票")

        # Step 4: 排名
        logger.info("[4/4] 生成排名...")
        if not predictions.empty:
            top50 = predictor.get_top_n(date.today(), 50)
            from app.models.stock import StockBasic
            from app.models.factor import FactorStore
            from app.models.stock_daily import StockDaily
            from app.models.model_record import ModelRecord

            # 从活跃模型获取特征重要性排名，确定"主力因子"
            model_record = (
                db.query(ModelRecord)
                .filter(ModelRecord.is_active == 1)
                .order_by(ModelRecord.id.desc())
                .first()
            )
            # 获取特征重要性最高的前20个因子（排除宏观因子）作为候选
            top_candidate_names = []
            if model_record and model_record.feature_importance_json:
                top_features = sorted(
                    model_record.feature_importance_json,
                    key=lambda x: x.get("importance", 0),
                    reverse=True,
                )
                # 排除宏观因子，因为它们对同一交易日所有股票都一样
                top_candidate_names = [
                    f["feature"] for f in top_features
                    if f.get("feature") and not f["feature"].startswith("macro_")
                ][:20]

            for item in top50:
                stock = db.query(StockBasic).filter(StockBasic.stock_code == item["stock_code"]).first()
                if stock:
                    item["stock_name"] = stock.stock_name
                    item["industry"] = stock.industry

                # 补充总市值（从原始数据计算：收盘价 × 总股本，避免使用标准化后的因子反推）
                item["market_cap"] = 0
                from app.models.balancesheet import Balancesheet
                daily = (
                    db.query(StockDaily)
                    .filter(
                        StockDaily.stock_code == item["stock_code"],
                        StockDaily.trade_date == trade_date,
                    )
                    .first()
                )
                bs = (
                    db.query(Balancesheet)
                    .filter(Balancesheet.stock_code == item["stock_code"])
                    .order_by(Balancesheet.end_date.desc())
                    .first()
                )
                if daily and daily.close and bs and bs.cap_stk:
                    total_shares = float(bs.cap_stk)
                    close_val = float(daily.close)
                    item["market_cap"] = round(close_val * total_shares, 2)

                # 补充主力因子：从模型认为最重要的候选因子中，
                # 取该股票"因子值绝对值最大"的前3个，不同股票展示不同因子
                factor_record = (
                    db.query(FactorStore)
                    .filter(
                        FactorStore.stock_code == item["stock_code"],
                        FactorStore.trade_date == trade_date,
                    )
                    .first()
                )
                if factor_record and top_candidate_names:
                    factor_values = []
                    for col in top_candidate_names:
                        val = getattr(factor_record, col, None)
                        if val is not None:
                            # contribution 使用因子值 × 重要性权重，综合衡量该因子对该股票的贡献
                            factor_values.append({"name": col, "contribution": float(val)})
                    # 按因子值绝对值从大到小排序，每只股票展示不同的前5个
                    factor_values.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                    item["top_factors"] = factor_values[:5]
                elif factor_record:
                    # 兜底：无候选因子，按因子值绝对值排序（排除宏观因子）
                    factor_cols = [
                        col.name for col in FactorStore.__table__.columns
                        if col.name not in ("id", "stock_code", "trade_date", "created_at")
                        and not col.name.startswith("macro_")
                    ]
                    factor_values = []
                    for col in factor_cols:
                        val = getattr(factor_record, col)
                        if val is not None:
                            factor_values.append({"name": col, "contribution": float(val)})
                    factor_values.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                    item["top_factors"] = factor_values[:5]
                else:
                    item["top_factors"] = []

            ranking_service = RankingService(db)
            ranking_service.save_ranking_snapshot(date.today(), top50)
            logger.info(f"✅ 排名生成完成: {len(top50)} 只股票")
        else:
            logger.info("无预测结果，跳过排名生成")

        logger.info("=== 流水线运行完成 ===")

    except Exception as e:
        logger.error(f"流水线运行失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    trade_date = sys.argv[1] if len(sys.argv) > 1 else None
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    run_pipeline(trade_date, top_n)
