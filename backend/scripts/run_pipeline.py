"""一键运行完整流水线"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date
from loguru import logger
from app.utils.db_utils import SessionLocal
from app.services.factor_engine import FactorEngine
from app.services.label_generator import LabelGenerator
from app.services.predictor import Predictor
from app.services.ranking_service import RankingService
from app.services.trainer import Trainer


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

        # Step 3: 预测
        logger.info("[3/4] 预测...")
        predictor = Predictor(db)
        predictions = predictor.predict_daily(trade_date)
        logger.info(f"✅ 预测完成: {len(predictions)} 只股票")

        # Step 4: 排名
        logger.info("[4/4] 生成排名...")
        if not predictions.empty:
            top50 = predictor.get_top_n(trade_date, 50)
            from app.models.stock import StockBasic
            for item in top50:
                stock = db.query(StockBasic).filter(StockBasic.stock_code == item["stock_code"]).first()
                if stock:
                    item["stock_name"] = stock.stock_name
                    item["industry"] = stock.industry

            ranking_service = RankingService(db)
            ranking_service.save_ranking_snapshot(date.today(), top50)
            logger.info(f"✅ 排名生成完成: {len(top50)} 只股票")

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
