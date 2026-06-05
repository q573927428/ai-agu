"""快速写入少量测试数据，用于前端验证"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date, timedelta
from loguru import logger
from app.utils.db_utils import SessionLocal
from app.models.stock import StockBasic
from app.models.stock_daily import StockDaily
from app.models.ranking import RankingSnapshot
from app.models.macro import MacroData

# 少量股票示例（真实A股代码）
DEMO_STOCKS = [
    {"stock_code": "600519", "stock_name": "贵州茅台", "industry": "食品饮料", "market": "SH"},
    {"stock_code": "000858", "stock_name": "五粮液",   "industry": "食品饮料", "market": "SZ"},
    {"stock_code": "600036", "stock_name": "招商银行", "industry": "银行",     "market": "SH"},
    {"stock_code": "601318", "stock_name": "中国平安", "industry": "保险",     "market": "SH"},
    {"stock_code": "000333", "stock_name": "美的集团", "industry": "家电",     "market": "SZ"},
    {"stock_code": "600276", "stock_name": "恒瑞医药", "industry": "医药生物", "market": "SH"},
    {"stock_code": "002415", "stock_name": "海康威视", "industry": "计算机",   "market": "SZ"},
    {"stock_code": "300750", "stock_name": "宁德时代", "industry": "电力设备", "market": "SZ"},
    {"stock_code": "600887", "stock_name": "伊利股份", "industry": "食品饮料", "market": "SH"},
    {"stock_code": "000002", "stock_name": "万科A",    "industry": "房地产",   "market": "SZ"},
    {"stock_code": "600030", "stock_name": "中信证券", "industry": "证券",     "market": "SH"},
    {"stock_code": "002594", "stock_name": "比亚迪",   "industry": "汽车",     "market": "SZ"},
    {"stock_code": "601166", "stock_name": "兴业银行", "industry": "银行",     "market": "SH"},
    {"stock_code": "000568", "stock_name": "泸州老窖", "industry": "食品饮料", "market": "SZ"},
    {"stock_code": "600900", "stock_name": "长江电力", "industry": "公用事业", "market": "SH"},
]


def seed_data():
    """填充测试数据"""
    db = SessionLocal()

    try:
        # 1. 写入股票基础信息
        logger.info("[1/5] 写入股票基础信息...")
        for s in DEMO_STOCKS:
            existing = db.query(StockBasic).filter(StockBasic.stock_code == s["stock_code"]).first()
            if not existing:
                db.add(StockBasic(**s, is_active=1, list_date=date(2020, 1, 1)))
        db.commit()
        logger.info(f"✅ 写入 {len(DEMO_STOCKS)} 只股票")

        # 2. 写入日行情数据（模拟过去60天+未来30天共90个交易日的收盘价）
        logger.info("[2/5] 写入日行情数据...")
        base_prices = {
            "600519": 1800, "000858": 150, "600036": 35, "601318": 45,
            "000333": 60, "600276": 45, "002415": 35, "300750": 200,
            "600887": 28, "000002": 12, "600030": 20, "002594": 260,
            "601166": 18, "000568": 200, "600900": 25,
        }
        import random
        random.seed(42)
        count = 0
        # 生成过去60天 + 未来30天，共90个交易日的数据
        trade_dates = []
        d = date.today()
        while len(trade_dates) < 90:
            if d.weekday() < 5:  # 周一到周五
                trade_dates.append(d)
            d += timedelta(days=1)
        # 找到最老的起始日期：从今天往前推60个交易日
        past_dates = []
        d = date.today()
        while len(past_dates) < 60:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                past_dates.append(d)
        past_dates.reverse()
        # 合并过去+未来
        all_dates = past_dates + trade_dates[:30]

        for td in all_dates:
            for s in DEMO_STOCKS:
                code = s["stock_code"]
                base = base_prices.get(code, 50)
                change = random.uniform(-0.03, 0.03)
                price = base * (1 + change * (all_dates.index(td) + 1) / 90)
                
                existing = db.query(StockDaily).filter(
                    StockDaily.stock_code == code,
                    StockDaily.trade_date == td
                ).first()
                if not existing:
                    db.add(StockDaily(
                        stock_code=code,
                        trade_date=td,
                        open=round(price * 0.998, 2),
                        high=round(price * 1.015, 2),
                        low=round(price * 0.985, 2),
                        close=round(price, 2),
                        pre_close=round(price * 0.997, 2),
                        volume=int(random.uniform(1e6, 5e7)),
                        amount=round(price * random.uniform(1e7, 5e7), 2),
                        turnover_rate=round(random.uniform(0.5, 5), 4),
                        pe_ttm=round(random.uniform(10, 50), 2),
                        pb=round(random.uniform(1, 10), 2),
                        total_mv=round(price * random.uniform(1e8, 5e9), 2),
                        float_mv=round(price * random.uniform(5e7, 2e9), 2),
                    ))
                    count += 1
        db.commit()
        logger.info(f"✅ 写入 {count} 条日行情记录")

        # 3. 写入宏观数据
        logger.info("[3/5] 写入宏观数据...")
        existing_macro = db.query(MacroData).first()
        if not existing_macro:
            db.add(MacroData(
                data_date=date.today(),
                gdp_yoy=5.2, cpi_yoy=0.3, pmi=50.8,
                m2_yoy=7.4, shibor_1m=1.85,
                bond_10y_yield=2.28, credit_spread=0.85,
                usdcny=7.24, market_sentiment=0.65,
            ))
            db.commit()
            logger.info("✅ 写入宏观数据")
        else:
            logger.info("⏭️ 宏观数据已存在，跳过")

        # 4. 直接写入排名快照（模拟 TOP15 排名，可直接展示）
        logger.info("[4/5] 写入排名快照...")
        today = date.today()
        # 先删除旧数据
        db.query(RankingSnapshot).filter(RankingSnapshot.snapshot_date == today).delete()
        
        for rank, s in enumerate(DEMO_STOCKS, 1):
            predicted_return = round(random.uniform(-0.03, 0.15), 4)
            snapshot = RankingSnapshot(
                snapshot_date=today,
                rank_position=rank,
                stock_code=s["stock_code"],
                stock_name=s["stock_name"],
                predicted_return=predicted_return,
                industry=s["industry"],
                market_cap=round(base_prices.get(s["stock_code"], 50) * random.uniform(1e8, 5e9), 2),
                top_factors_json=[
                    {"name": "动量因子", "contribution": round(random.uniform(0.1, 0.3), 4)},
                    {"name": "估值因子", "contribution": round(random.uniform(0.05, 0.2), 4)},
                    {"name": "盈利因子", "contribution": round(random.uniform(0.02, 0.1), 4)},
                ],
            )
            db.add(snapshot)
        db.commit()
        logger.info(f"✅ 写入 {len(DEMO_STOCKS)} 条排名快照")

        logger.info("[5/5] 清理临时数据...")
        # 仅清理今天之前60天以外的旧数据，保留未来数据
        sixty_days_ago = today - timedelta(days=60)
        deleted = db.query(StockDaily).filter(
            StockDaily.trade_date < sixty_days_ago,
            StockDaily.trade_date < today,
        ).delete()
        db.commit()
        logger.info(f"✅ 清理了 {deleted} 条旧日行情记录")

        logger.info("=== 测试数据填充完成! ===")

    except Exception as e:
        logger.error(f"填充失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()