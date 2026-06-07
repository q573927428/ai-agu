"""修复数据库数据：修正模型路径、转换旧预测数据、清理旧排名"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from datetime import date
from app.models.model_record import ModelRecord
from app.models.prediction import Prediction
from app.models.ranking import RankingSnapshot
from app.config import settings
from sqlalchemy import func, text

db = SessionLocal()

# 1. 修正模型路径
m = db.query(ModelRecord).filter(ModelRecord.is_active == 1).first()
if m:
    old_path = m.model_path
    filename = os.path.basename(old_path)
    new_path = os.path.join(settings.model_dir, filename)
    m.model_path = new_path
    db.commit()
    print(f'模型路径修正: {old_path} -> {new_path}')
    print(f'文件实际存在: {os.path.exists(new_path)}')

# 2. 清理旧预测数据（百分数格式，需要除以100）
print(f'\n旧预测数据: {db.query(Prediction).count()} 条')
max_pred = db.query(func.max(Prediction.predicted_return)).scalar()
if max_pred and abs(max_pred) > 5:
    print(f'最大预测值={max_pred}, 确认为百分数格式, 执行除以100转换...')
    db.execute(text('UPDATE prediction SET predicted_return = predicted_return / 100.0, rank_score = rank_score / 100.0'))
    db.commit()
    max_pred_new = db.query(func.max(Prediction.predicted_return)).scalar()
    print(f'转换后最大预测值={max_pred_new}')
else:
    print(f'最大预测值={max_pred}, 格式正常, 无需转换')

# 3. 清理旧排名快照（让流水线重新生成）
today = date.today()
old_snap = db.query(RankingSnapshot).filter(RankingSnapshot.snapshot_date == today).all()
print(f'\n今日排名快照: {len(old_snap)} 条, 已清理')
db.query(RankingSnapshot).filter(RankingSnapshot.snapshot_date == today).delete()
db.commit()

db.close()
print('\n数据库修复完成')