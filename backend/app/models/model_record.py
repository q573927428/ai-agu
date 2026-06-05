"""模型训练记录表"""
from sqlalchemy import Column, String, Date, Integer, BigInteger, DECIMAL, DateTime, JSON
from sqlalchemy.sql import func
from .base import Base


class ModelRecord(Base):
    __tablename__ = "model_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_version = Column(String(50), nullable=False, comment="模型版本")
    train_date = Column(Date, nullable=False, comment="训练日期")
    data_start_date = Column(Date, comment="训练数据起始日期")
    data_end_date = Column(Date, comment="训练数据截止日期")
    num_samples = Column(Integer, comment="训练样本数")
    num_features = Column(Integer, comment="特征数量")
    params_json = Column(JSON, comment="超参数JSON")
    train_ic = Column(DECIMAL(10, 6), comment="训练集IC")
    valid_ic = Column(DECIMAL(10, 6), comment="验证集IC")
    train_rank_ic = Column(DECIMAL(10, 6), comment="训练集RankIC")
    valid_rank_ic = Column(DECIMAL(10, 6), comment="验证集RankIC")
    feature_importance_json = Column(JSON, comment="特征重要性JSON")
    model_path = Column(String(255), comment="模型文件路径")
    is_active = Column(Integer, default=0, comment="是否为当前使用模型")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")