"""检查数据库表结构"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.utils.db_utils import engine

with engine.connect() as conn:
    tables = conn.execute(text("SHOW TABLES")).fetchall()
    print("数据库中的表:")
    for t in tables:
        print(f"  - {t[0]}")

    # 检查 index_daily 表结构
    if ("index_daily",) in tables:
        print("\nindex_daily 表结构:")
        cols = conn.execute(text("DESCRIBE index_daily")).fetchall()
        for c in cols:
            print(f"  {c[0]:15s} {c[1]:20s}")