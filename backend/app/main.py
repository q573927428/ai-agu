"""FastAPI 应用入口"""
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from app.api.v1.router import router as v1_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 A股量化选股平台启动中...")
    logger.info(f"环境: {settings.app_env}")
    logger.info(f"数据库: {settings.database_url}")

    # 启动定时任务（生产环境）
    if settings.app_env == "production":
        try:
            from app.scheduler.jobs import start_scheduler
            # scheduler will be started separately
        except Exception as e:
            logger.warning(f"定时任务启动失败: {e}")

    yield

    logger.info("🛑 应用关闭")


app = FastAPI(
    title="A股量化选股平台 API",
    description="基于 LightGBM 的 A 股量化选股系统，提供实时排名、因子分析、预测数据",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(v1_router)


# 健康检查
@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0"}


# 市场概览
@app.get("/api/v1/market/overview")
async def market_overview():
    """市场概览数据"""
    return {
        "code": 0,
        "data": {
            "market_index": {
                "sh_index": 0,
                "sh_change": 0,
                "sz_index": 0,
                "sz_change": 0,
            },
            "market_stats": {
                "up_count": 0,
                "down_count": 0,
                "flat_count": 0,
                "advance_decline_ratio": 0,
            },
            "model_status": {
                "model_version": "N/A",
                "last_train_date": None,
                "latest_ic": 0,
                "is_active": False,
            },
        },
        "message": "success",
    }


# 模型状态
@app.get("/api/v1/model/status")
async def model_status():
    """模型状态信息"""
    from app.utils.db_utils import SessionLocal
    from app.models.model_record import ModelRecord

    db = SessionLocal()
    try:
        record = db.query(ModelRecord).filter(ModelRecord.is_active == 1).first()
        if record:
            return {
                "code": 0,
                "data": {
                    "model_version": record.model_version,
                    "last_train_date": str(record.train_date) if record.train_date else None,
                    "latest_ic": float(record.valid_ic or 0),
                    "is_active": bool(record.is_active),
                    "num_samples": record.num_samples,
                    "num_features": record.num_features,
                },
                "message": "success",
            }
        return {"code": 0, "data": None, "message": "暂无模型"}
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)