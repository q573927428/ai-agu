"""诊断数据库状态"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from app.models.stock_daily import StockDaily
from app.models.prediction import Prediction
from app.models.ranking import RankingSnapshot
from app.models.model_record import ModelRecord
from app.models.factor import FactorStore
from datetime import date

db = SessionLocal()

print("=== 日行情数据 ===")
dates = db.query(StockDaily.trade_date).distinct().order_by(StockDaily.trade_date.desc()).limit(5).all()
print(f"最近的交易日: {[str(d[0]) for d in dates]}")
today = date.today()
has_today = db.query(StockDaily).filter(StockDaily.trade_date == today).first()
print(f"今天({today})是否有行情数据: {has_today is not None}")
total = db.query(StockDaily).count()
print(f"日行情总记录数: {total}")

print("\n=== 预测表 ===")
pred_count = db.query(Prediction).count()
print(f"预测表记录数: {pred_count}")
if pred_count > 0:
    pred_max = db.query(Prediction).order_by(Prediction.predicted_return.desc()).first()
    pred_min = db.query(Prediction).order_by(Prediction.predicted_return.asc()).first()
    print(f"最大预测收益率: {pred_max.predicted_return}")
    print(f"最小预测收益率: {pred_min.predicted_return}")
    print(f"示例前5条:")
    top5 = db.query(Prediction).order_by(Prediction.predicted_return.desc()).limit(5).all()
    for p in top5:
        print(f"  {p.stock_code} 收益率={p.predicted_return}")

print("\n=== 排名快照 ===")
rank_count = db.query(RankingSnapshot).count()
print(f"排名快照记录数: {rank_count}")
if rank_count > 0:
    snap_dates = db.query(RankingSnapshot.snapshot_date).distinct().order_by(RankingSnapshot.snapshot_date.desc()).all()
    print(f"快照日期: {[str(d[0]) for d in snap_dates]}")
    latest = snap_dates[0][0]
    cnt = db.query(RankingSnapshot).filter(RankingSnapshot.snapshot_date == latest).count()
    print(f"最新日期({latest})排名数: {cnt}")
    s1 = db.query(RankingSnapshot).filter(RankingSnapshot.snapshot_date == latest).order_by(RankingSnapshot.rank_position).first()
    if s1:
        print(f"TOP1: {s1.stock_code} {s1.stock_name} 收益率={s1.predicted_return} 市值={s1.market_cap}")

print("\n=== 因子表 ===")
factor_count = db.query(FactorStore).count()
print(f"因子表记录数: {factor_count}")
if factor_count > 0:
    f_dates = db.query(FactorStore.trade_date).distinct().order_by(FactorStore.trade_date.desc()).limit(3).all()
    print(f"最近因子日期: {[str(d[0]) for d in f_dates]}")

print("\n=== 模型记录 ===")
model_count = db.query(ModelRecord).count()
print(f"模型记录数: {model_count}")
if model_count > 0:
    m = db.query(ModelRecord).order_by(ModelRecord.id.desc()).first()
    print(f"最新模型版本: {m.model_version}")
    print(f"模型路径: {m.model_path}")
    print(f"是否活跃(1=活跃): {m.is_active}")
    print(f"文件是否确实存在: {os.path.exists(m.model_path) if m.model_path else '无路径'}")

db.close()