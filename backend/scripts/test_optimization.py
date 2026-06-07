"""测试优化后的因子计算速度"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from app.utils.db_utils import SessionLocal
from app.services.factor_engine import FactorEngine


def main():
    # 1. 检查数据库中有哪些交易日
    db = SessionLocal()
    try:
        from app.models.stock_daily import StockDaily
        from sqlalchemy import func

        result = (
            db.query(StockDaily.trade_date)
            .distinct()
            .order_by(StockDaily.trade_date.desc())
            .first()
        )
        if result:
            latest_date = result[0]
            count = db.query(StockDaily.trade_date).distinct().count()
            stock_count = db.query(StockDaily.stock_code).filter(
                StockDaily.trade_date == latest_date
            ).distinct().count()

            print(f"最新交易日: {latest_date}")
            print(f"总交易日数: {count}")
            print(f"该日股票数量: {stock_count}")

            # 2. 测试因子计算速度（限制前100只股票）
            print(f"\n--- 测试因子计算（限制100只，日期: {latest_date}）---")
            start = time.time()
            engine = FactorEngine(db)
            df = engine.compute_all(str(latest_date), top_n=100)
            elapsed = time.time() - start

            print(f"因子计算完成: {len(df)} 只股票")
            print(f"因子数量: {len(df.columns) - 2} 个")
            print(f"耗时: {elapsed:.2f} 秒")

            if not df.empty:
                print(f"\n前5行数据预览:")
                print(df.head(5).to_string())
        else:
            print("数据库无数据，请先运行 fetch 脚本导入数据！")

    finally:
        db.close()


if __name__ == "__main__":
    main()