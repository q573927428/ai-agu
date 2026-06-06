"""
找出 Tushare Pro 财务接口实际返回列名和字段映射的差异
用法: python scripts/fix_field_map.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
ts.set_token(os.getenv("TUSHARE_TOKEN"))
pro = ts.pro_api()

# 实际列名对照
api_list = [
    ("income", pro.income),
    ("balancesheet", pro.balancesheet),
    ("cashflow", pro.cashflow),
    ("fina_indicator", pro.fina_indicator),
]

# 我们模型的字段名（目标列）
from app.models.income import Income
from app.models.balancesheet import Balancesheet
from app.models.cashflow import Cashflow
from app.models.fina_indicator import FinaIndicator

models = {
    "income": Income,
    "balancesheet": Balancesheet,
    "cashflow": Cashflow,
    "fina_indicator": FinaIndicator,
}

for api_name, api_func in api_list:
    print(f"\n{'='*60}")
    print(f"📊 {api_name}")
    print(f"{'='*60}")
    
    df = api_func(ts_code='000001.SZ')
    if df is None or df.empty:
        print("无数据")
        continue
    
    actual_cols = set(df.columns)
    model = models[api_name]
    target_cols = {c.name for c in model.__table__.columns}
    
    print(f"实际返回列数: {len(actual_cols)}")
    print(f"模型目标列数: {len(target_cols)}")
    
    # 找出可以在模型中找到对应关系的列
    matched = []
    unmatched = []
    for col in sorted(actual_cols):
        if col in target_cols:
            matched.append(col)
        elif col not in ('ts_code', 'ann_date', 'f_ann_date', 'end_type', 'comp_type', 'update_flag'):
            unmatched.append(col)
    
    print(f"\n✅ 可直接匹配的列 ({len(matched)}):")
    for c in matched:
        print(f"  {c}")
    
    print(f"\n⚠️ 需映射的列 ({len(unmatched)}):")
    for c in unmatched:
        print(f"  {c}")