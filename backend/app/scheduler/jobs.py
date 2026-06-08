"""APScheduler 定时任务定义"""
from datetime import datetime, date
from loguru import logger
from app.utils.db_utils import SessionLocal
from app.utils.date_utils import is_trade_day, get_latest_trade_day
from app.services.data_fetcher import DataFetcher
from app.services.factor_engine import FactorEngine
from app.services.label_generator import LabelGenerator
from app.services.predictor import Predictor
from app.services.ranking_service import RankingService
from app.services.trainer import Trainer


async def fetch_stock_data_job():
    """J01: 采集当日全市场股票日数据"""
    if not is_trade_day(datetime.now()):
        logger.info("非交易日，跳过数据采集")
        return

    logger.info("开始采集当日股票数据...")
    db = SessionLocal()
    try:
        fetcher = DataFetcher()
        trade_date = date.today().strftime("%Y-%m-%d")
        df = await fetcher.fetch_stock_daily_batch(trade_date)
        logger.info(f"数据采集完成: {len(df)} 条")
    finally:
        db.close()


async def compute_factors_job():
    """J04: 计算全市场因子"""
    if not is_trade_day(datetime.now()):
        return

    logger.info("开始计算因子...")
    db = SessionLocal()
    try:
        engine = FactorEngine(db)
        trade_date = date.today().strftime("%Y-%m-%d")
        df = engine.compute_all(trade_date)
        if not df.empty:
            engine.save_factors(df)
        logger.info(f"因子计算完成: {len(df)} 只股票")
    finally:
        db.close()


async def daily_predict_job():
    """J06: 每日预测全市场股票"""
    if not is_trade_day(datetime.now()):
        return

    logger.info("开始每日预测...")
    db = SessionLocal()
    try:
        predictor = Predictor(db)
        trade_date = date.today().strftime("%Y-%m-%d")
        df = predictor.predict_daily(trade_date)
        logger.info(f"预测完成: {len(df)} 只股票")
    finally:
        db.close()


async def generate_ranking_job():
    """J07: 生成TOP10排名快照"""
    if not is_trade_day(datetime.now()):
        return

    logger.info("开始生成排名...")
    db = SessionLocal()
    try:
        predictor = Predictor(db)
        ranking_service = RankingService(db)
        trade_date = date.today().strftime("%Y-%m-%d")
        top50 = predictor.get_top_n(trade_date, 50)

        # 获取股票名称和行业
        from app.models.stock import StockBasic
        for item in top50:
            stock = db.query(StockBasic).filter(StockBasic.stock_code == item["stock_code"]).first()
            if stock:
                item["stock_name"] = stock.stock_name
                item["industry"] = stock.industry

        ranking_service.save_ranking_snapshot(date.today(), top50)
        logger.info("排名快照生成完成")
    finally:
        db.close()


async def train_model_job():
    """J08: 每月模型重训"""
    logger.info("开始模型训练...")
    db = SessionLocal()
    try:
        trainer = Trainer(db)
        end_date = date.today().strftime("%Y-%m-%d")
        # 默认使用过去3年的数据
        start_date = f"{int(end_date[:4]) - 3}{end_date[4:]}"

        result = trainer.train(start_date, end_date)
        logger.info(f"模型训练完成: {result}")
    finally:
        db.close()