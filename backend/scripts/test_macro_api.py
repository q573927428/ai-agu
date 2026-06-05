"""测试宏观数据API接口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
ts.set_token(os.getenv("TUSHARE_TOKEN", ""))
pro = ts.pro_api()

# 测试 cn_m (M2)
print("=" * 50)
print("测试 cn_m (M2货币供应量)")
print("=" * 50)
try:
    df = pro.cn_m(fields='month,m2,m2_yoy')
    if df is not None and not df.empty:
        last = df.iloc[-1]
        print(f"最新月份: {last['month']}, M2同比: {last.get('m2_yoy')}")
    else:
        print("cn_m 返回空数据")
except Exception as e:
    print(f"cn_m 失败: {e}")

# 测试 cn_pmi
print("\n" + "=" * 50)
print("测试 cn_pmi (制造业PMI)")
print("=" * 50)
try:
    df = pro.cn_pmi(fields='month,pmi010000')
    if df is not None and not df.empty:
        last = df.iloc[-1]
        print(f"最新月份: {last['month']}, 制造业PMI: {last.get('pmi010000')}")
    else:
        print("cn_pmi 返回空数据")
except Exception as e:
    print(f"cn_pmi 失败: {e}")

# 测试 sf_month
print("\n" + "=" * 50)
print("测试 sf_month (社融存量)")
print("=" * 50)
try:
    df = pro.sf_month(fields='month,stk_endval')
    if df is not None and not df.empty:
        last = df.iloc[-1]
        print(f"最新月份: {last['month']}, 社融存量期末值: {last.get('stk_endval')}")
    else:
        print("sf_month 返回空数据")
except Exception as e:
    print(f"sf_month 失败: {e}")

# 测试 us_tycr
print("\n" + "=" * 50)
print("测试 us_tycr (美国国债收益率)")
print("=" * 50)
try:
    from datetime import date
    today_str = date.today().strftime("%Y%m%d")
    df = pro.us_tycr(start_date=today_str, end_date=today_str)
    if df is not None and not df.empty:
        last = df.iloc[-1]
        print(f"3月期: {last.get('m3')}, 2年期: {last.get('y2')}, 10年期: {last.get('y10')}")
    else:
        print("us_tycr 当日无数据")
except Exception as e:
    print(f"us_tycr 失败: {e}")

print("\n✅ 测试完成")