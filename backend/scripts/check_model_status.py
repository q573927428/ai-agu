"""检查模型状态"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db_utils import SessionLocal
from app.models.model_record import ModelRecord
from app.models.factor import FactorStore
from app.models.prediction import Prediction

db = SessionLocal()
try:
    mr = db.query(ModelRecord).filter(ModelRecord.is_active == 1).first()
    print(f"活跃模型: {mr.model_version if mr else '无'}")
    print(f"模型路径: {mr.model_path if mr else '无'}")
    print(f"模型文件存在: {os.path.exists(mr.model_path) if mr and mr.model_path else False}")
    print(f"因子表记录数: {db.query(FactorStore).count()}")
    print(f"预测表记录数: {db.query(Prediction).count()}")
    records = db.query(ModelRecord).count()
    print(f"模型记录总数: {records}")
    if mr:
        print(f"模型版本: {mr.model_version}")
        print(f"训练日期: {mr.train_date}")
        print(f"样本数: {mr.num_samples}")
        print(f"特征数: {mr.num_features}")
        print(f"Valid IC: {mr.valid_ic}")
finally:
    db.close()