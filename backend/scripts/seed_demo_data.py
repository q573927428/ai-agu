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
    {"ts_code": "600519.SH", "stock_code": "600519", "stock_name": "贵州茅台", "area": "贵州", "industry": "食品饮料", "cnspell": "GZMT", "market": "主板", "exchange": "SSE", "list_date": "2001-08-27", "is_hs": "H"},
    {"ts_code": "000858.SZ", "stock_code": "000858", "stock_name": "五粮液",   "area": "四川", "industry": "食品饮料", "cnspell": "WLY", "market": "主板", "exchange": "SZSE", "list_date": "1998-04-27", "is_hs": "H"},
    {"ts_code": "600036.SH", "stock_code": "600036", "stock_name": "招商银行", "area": "深圳", "industry": "银行",     "cnspell": "ZSYH", "market": "主板", "exchange": "SSE", "list_date": "2002-04-09", "is_hs": "H"},
    {"ts_code": "601318.SH", "stock_code": "601318", "stock_name": "中国平安", "area": "深圳", "industry": "保险",     "cnspell": "ZGPA", "market": "主板", "exchange": "SSE", "list_date": "2007-03-01", "is_hs": "H"},
    {"ts_code": "000333.SZ", "stock_code": "000333", "stock_name": "美的集团", "area": "广东", "industry": "家电",     "cnspell": "MDJT", "market": "主板", "exchange": "SZSE", "list_date": "2013-09-18", "is_hs": "H"},
    {"ts_code": "600276.SH", "stock_code": "600276", "stock_name": "恒瑞医药", "area": "江苏", "industry": "医药生物", "cnspell": "HRYY", "market": "主板", "exchange": "SSE", "list_date": "2000-10-18", "is_hs": "H"},
    {"ts_code": "002415.SZ", "stock_code": "002415", "stock_name": "海康威视", "area": "浙江", "industry": "计算机",   "cnspell": "HKWS", "market": "中小板", "exchange": "SZSE", "list_date": "2010-05-28", "is_hs": "H"},
    {"ts_code": "300750.SZ", "stock_code": "300750", "stock_name": "宁德时代", "area": "福建", "industry": "电力设备", "cnspell": "NDSD", "market": "创业板", "exchange": "SZSE", "list_date": "2018-06-11", "is_hs": "H"},
    {"ts_code": "600887.SH", "stock_code": "600887", "stock_name": "伊利股份", "area": "内蒙古", "industry": "食品饮料", "cnspell": "YLGF", "market": "主板", "exchange": "SSE", "list_date": "1996-03-12", "is_hs": "H"},
    {"ts_code": "000002.SZ", "stock_code": "000002", "stock_name": "万科A",    "area": "深圳", "industry": "房地产",   "cnspell": "WKA", "market": "主板", "exchange": "SZSE", "list_date": "1991-01-29", "is_hs": "H"},
    {"ts_code": "600030.SH", "stock_code": "600030", "stock_name": "中信证券", "area": "广东", "industry": "证券",     "cnspell": "ZXZQ", "market": "主板", "exchange": "SSE", "list_date": "2003-01-06", "is_hs": "H"},
    {"ts_code": "002594.SZ", "stock_code": "002594", "stock_name": "比亚迪",   "area": "深圳", "industry": "汽车",     "cnspell": "BYD", "market": "主板", "exchange": "SZSE", "list_date": "2011-06-30", "is_hs": "H"},
    {"ts_code": "601166.SH", "stock_code": "601166", "stock_name": "兴业银行", "area": "福建", "industry": "银行",     "cnspell": "XYYH", "market": "主板", "exchange": "SSE", "list_date": "2007-02-05", "is_hs": "H"},
    {"ts_code": "000568.SZ", "stock_code": "000568", "stock_name": "泸州老窖", "area": "四川", "industry": "食品饮料", "cnspell": "LZLJ", "market": "主板", "exchange": "SZSE", "list_date": "1994-05-09", "is_hs": "H"},
    {"ts_code": "600900.SH", "stock_code": "600900", "stock_name": "长江电力", "area": "北京", "industry": "公用事业", "cnspell": "CJDL", "market": "主板", "exchange": "SSE", "list_date": "2003-11-18", "is_hs": "H"},
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
                s_copy = dict(s)
                if isinstance(s_copy.get("list_date"), str):
                    s_copy["list_date"] = datetime.strptime(s_copy["list_date"], "%Y-%m-%d").date()
                db.add(StockBasic(**s_copy, is_active=1))
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
                
                pct_chg = random.uniform(-3.0, 3.0)
                pre_close = round(price / (1 + pct_chg / 100), 2)
                change = round(price - pre_close, 3)
                existing = db.query(StockDaily).filter(
                    StockDaily.stock_code == code,
                    StockDaily.trade_date == td
                ).first()
                if not existing:
                    db.add(StockDaily(
                        stock_code=code,
                        trade_date=td,
                        open=round(price * 0.998, 3),
                        high=round(price * 1.015, 3),
                        low=round(price * 0.985, 3),
                        close=round(price, 3),
                        pre_close=pre_close,
                        change=change,
                        pct_chg=round(pct_chg, 6),
                        volume=int(random.uniform(1e6, 5e7)),
                        amount=round(price * random.uniform(1e7, 5e7), 2),
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
                gdp_yoy=5.2, gdp=1260582.00,
                cpi_yoy=0.3, cpi_val=112.50, ppi_yoy=0.1,
                pmi=50.8,
                m2_yoy=7.4,
                shibor_on=1.32, shibor_1w=1.38, shibor_1m=1.85, shibor_1y=1.46,
                hgt=179961.34, sgt=224809.37, north_flow=404770.71,
                margin_balance=15000.00,
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