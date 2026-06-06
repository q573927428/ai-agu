"""检查财务数据表中的非空数据量"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    for t in ['income', 'balancesheet', 'cashflow', 'fina_indicator']:
        r = db.execute(text(f'SELECT COUNT(*), MIN(end_date), MAX(end_date) FROM `{t}`')).fetchone()
        count = r[0]
        if count > 0:
            # 查看关键字段非空的数量
            if t == 'income':
                r2 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE revenue IS NOT NULL")).fetchone()
                r3 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE net_profit IS NOT NULL")).fetchone()
            elif t == 'balancesheet':
                r2 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE total_assets IS NOT NULL")).fetchone()
                r3 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE total_liab IS NOT NULL")).fetchone()
            elif t == 'cashflow':
                r2 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE net_oper_cash IS NOT NULL")).fetchone()
                r3 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE free_cashflow IS NOT NULL")).fetchone()
            elif t == 'fina_indicator':
                r2 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE roe IS NOT NULL")).fetchone()
                r3 = db.execute(text(f"SELECT COUNT(*) FROM `{t}` WHERE roa IS NOT NULL")).fetchone()
            print(f"✅ {t}: {count} 条 ({r[1]} ~ {r[2]}), 有数据: {r2[0]}条, {r3[0]}条")
        else:
            print(f"❌ {t}: 0 条")
except Exception as e:
    print(f"错误: {e}")
finally:
    db.close()