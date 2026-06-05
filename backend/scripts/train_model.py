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

    # 2. 计算因子
    existing = set(r[0] for r in db.query(FactorStore.trade_date).distinct().all())
    engine = FactorEngine(db)
    for td in dates:
        td_str = td.strftime("%Y-%m-%d") if hasattr(td, 'strftime') else str(td)
        if td_str in {d.strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d) for d in existing}:
            continue
        df = engine.compute_all(td_str, top_n=50)
        if df is not None and not df.empty:
            engine.save_factors(df)

    # 3. 检查因子
    fdates = [r[0] for r in db.query(FactorStore.trade_date).distinct().order_by(FactorStore.trade_date).all()]
    logger.info(f"因子日期数: {len(fdates)}")
    for d in fdates:
        logger.info(f"  {d}")
    if len(fdates) < 3:
        logger.error("因子数据不足")
        exit(1)

    # 4. 训练
    start = str(fdates[0])
    end = str(fdates[-3])
    logger.info(f"训练范围: {start} ~ {end}")
    trainer = Trainer(db)
    result = trainer.train(start, end)
    logger.info(f"训练结果: {result['status']} 版本={result.get('model_version','?')}")

except Exception as e:
    logger.error(f"失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()