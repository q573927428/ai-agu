"""一键生成多日因子并训练模型"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from loguru import logger
from app.utils.db_utils import SessionLocal
from app.models.stock_daily import StockDaily
from app.models.factor import FactorStore
from app.services.factor_engine import FactorEngine
from app.services.trainer import Trainer

db = SessionLocal()
try:
    # 1. 获取所有交易日
    dates = [r[0] for r in db.query(StockDaily.trade_date).distinct().order_by(StockDaily.trade_date).all()]
    logger.info(f"交易日: {len(dates)} 天")

    # 2. 计算因子（仅计算最近3年的日期）
    THREE_YEARS_TRADING_DAYS = 1500  # 约6年（A股年均250个交易日）
    recent_dates = dates[-min(len(dates), THREE_YEARS_TRADING_DAYS):]
    logger.info(f"计算因子范围: {recent_dates[0]} ~ {recent_dates[-1]}, 共 {len(recent_dates)} 个交易日")

    existing = set(r[0] for r in db.query(FactorStore.trade_date).distinct().all())
    engine = FactorEngine(db)
    for td in recent_dates:
        td_str = td.strftime("%Y-%m-%d") if hasattr(td, 'strftime') else str(td)
        if td_str in {d.strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d) for d in existing}:
            continue
        df = engine.compute_all(td_str, top_n=50)
        if df is not None and not df.empty:
            engine.save_factors(df)

    # 3. 检查因子（仅最近3年）
    fdates = [r[0] for r in db.query(FactorStore.trade_date).filter(FactorStore.trade_date >= recent_dates[0]).distinct().order_by(FactorStore.trade_date).all()]
    logger.info(f"因子日期数: {len(fdates)}, 范围: {fdates[0]} ~ {fdates[-1]}")
    if len(fdates) < 3:
        logger.error("因子数据不足")
        exit(1)

    # 4. 训练20日预测模型（最近3年数据）
    start = str(fdates[0])
    end = str(fdates[-3])
    logger.info(f"训练范围: {start} ~ {end}")
    trainer = Trainer(db)
    result = trainer.train(start, end)
    if result.get("note") == "multi-model ensemble":
        logger.info(
            f"训练结果: {result['status']} "
            f"集成子模型数={result.get('ensemble_size', '?')} "
            f"IC均值={result.get('valid_ic_mean', '?'):.4f}"
        )
    else:
        logger.info(f"训练结果: {result['status']} 版本={result.get('model_version','?')}")

    # 5. 训练1日预测模型（使用同样范围的因子数据，但标签为次日收益率）
    logger.info(f"\n{'='*50}")
    logger.info("训练1日预测模型...")
    logger.info(f"{'='*50}")
    result_1d = trainer.train_1d(start, end)
    if result_1d.get("note") == "1d multi-model ensemble":
        logger.info(
            f"1日预测训练结果: {result_1d['status']} "
            f"集成子模型数={result_1d.get('ensemble_size', '?')} "
            f"IC均值={result_1d.get('valid_ic_mean', '?'):.4f}"
        )
    else:
        logger.info(f"1日预测训练结果: {result_1d['status']} 版本={result_1d.get('model_version','?')}")

except Exception as e:
    logger.error(f"失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()