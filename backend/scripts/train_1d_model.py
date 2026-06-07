"""训练1日预测模型"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from app.utils.db_utils import SessionLocal
from app.services.trainer import Trainer


def train_1d():
    db = SessionLocal()
    try:
        # 使用最近一年的数据训练（2025年6月 ~ 2026年6月）
        start_date = "2025-06-01"
        end_date = "2026-06-05"
        
        logger.info(f"=== 开始训练1日预测模型: {start_date} ~ {end_date} ===")
        
        trainer = Trainer(db)
        result = trainer.train_1d(start_date=start_date, end_date=end_date)
        
        if result.get("status") == "success":
            logger.info(
                f"✅ 1日模型训练成功: "
                f"{result['ensemble_size']} 个子模型, "
                f"IC均值={result['valid_ic_mean']:.4f}"
            )
            for ver in result.get("model_versions", []):
                logger.info(f"   📦 {ver}")
        else:
            logger.error(f"❌ 1日模型训练失败: {result.get('message', '未知错误')}")
            
    except Exception as e:
        logger.error(f"训练过程异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    train_1d()