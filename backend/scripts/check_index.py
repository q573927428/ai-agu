"""检查指数数据"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils.db_utils import SessionLocal
from app.models.index_daily import IndexDaily
from app.models.stock_daily import StockDaily

db = SessionLocal()

# 检查指数数据
index_count = db.query(IndexDaily).count()
print(f"指数数据条数: {index_count}")

if index_count > 0:
    # 查看最新数据
    latest = db.query(IndexDaily).order_by(IndexDaily.trade_date.desc()).first()
    print(f"最新指数: {latest.ts_code} {latest.trade_date} close={latest.close} pct_chg={latest.pct_chg}")

# 检查stock_daily最新交易日
latest_date = db.query(db.query(StockDaily).order_by(StockDaily.trade_date.desc()).limit(1).subquery().c.trade_date).scalar()
print(f"最新个股交易日: {latest_date}")

db.close()