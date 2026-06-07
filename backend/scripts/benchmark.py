"""快速基准测试 - 不输出DataFrame"""
import time
import sys

sys.path.insert(0, ".")
from app.utils.db_utils import SessionLocal
from app.services.factor_engine import FactorEngine

db = SessionLocal()
engine = FactorEngine(db)
t0 = time.perf_counter()
df = engine.compute_all("2026-06-05", top_n=100)
t1 = time.perf_counter()
print(f">>> 100只股票耗时: {t1-t0:.3f}秒, 共{len(df)}只, {len(df.columns)-2}个因子")
db.close()