"""检查数据库状态"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from app.models.stock_daily import StockDaily
from app.models.stock import StockBasic
from app.models.macro import MacroData

db = SessionLocal()
try:
    stock_count = db.query(StockBasic).count()
    daily_count = db.query(StockDaily).count()
    macro_count = db.query(MacroData).count()
    
    dates = db.query(StockDaily.trade_date).distinct().order_by(StockDaily.trade_date.desc()).limit(5).all()
    codes = db.query(StockDaily.stock_code).distinct().count()
    
    print(f"StockBasic: {stock_count}")
    print(f"StockDaily: {daily_count}")
    print(f"MacroData: {macro_count}")
    print(f"StockDaily 唯一股票数: {codes}")
    print(f"最近5个交易日: {[str(d[0]) for d in dates]}")
    
    # 检查2026-06-05的数据
    today_data = db.query(StockDaily).filter(StockDaily.trade_date == "2026-06-05").count()
    print(f"2026-06-05 记录数: {today_data}")
finally:
    db.close()