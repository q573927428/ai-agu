"""诊断4张财务表中哪些字段全部为NULL - 纯文本输出"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    for table_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator']:
        print(f"\n{'='*60}")
        print(f"[{table_name}]")
        print(f"{'='*60}")

        cols = db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).fetchall()
        total_rows = db.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()[0]
        print(f"总行数: {total_rows}")

        if total_rows == 0:
            print("  空表，跳过")
            continue

        all_null_fields = []
        partial_null_fields = []
        ok_fields = []

        for col in cols:
            col_name = col[0]
            if col_name in ('id', 'stock_code', 'end_date', 'report_type', 'updated_at'):
                continue

            r = db.execute(text(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{col_name}` IS NOT NULL")).fetchone()
            non_null = r[0]

            if non_null == 0:
                all_null_fields.append(col_name)
            elif non_null < total_rows:
                partial_null_fields.append((col_name, non_null, total_rows - non_null))
            else:
                ok_fields.append(col_name)

        print(f"\n全部为NULL的字段 ({len(all_null_fields)}):")
        for f in all_null_fields:
            print(f"  [NULL] {f}")

        print(f"\n部分为NULL的字段 ({len(partial_null_fields)}):")
        for f, ok, null in partial_null_fields:
            pct = ok * 100 // total_rows
            print(f"  [{pct}%] {f}: {ok}/{total_rows}")

        print(f"\n全部非空的字段 ({len(ok_fields)}):")
        for f in ok_fields:
            print(f"  [OK] {f}")

        # 对全部NULL字段，看Tushare实际返回了什么值
        if all_null_fields:
            print(f"\n  第1行样例数据:")
            sample = db.execute(text(f"SELECT * FROM `{table_name}` LIMIT 1")).fetchone()
            if sample:
                col_meta = db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).fetchall()
                for i, col in enumerate(col_meta):
                    col_name = col[0]
                    if col_name in all_null_fields:
                        print(f"    {col_name} = {sample[i]}")

finally:
    db.close()