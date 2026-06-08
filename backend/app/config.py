"""应用配置管理"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MySQL (请通过 .env 设置)
    mysql_root_password: str = ""
    mysql_password: str = ""
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "agu_quant"

    # Backend (请通过 .env 设置 DATABASE_URL)
    database_url: str = ""
    app_env: str = "development"
    log_level: str = "INFO"

    # Model
    model_dir: str = ""  # 在 __init__ 中设为绝对路径
    model_version: str = "v1.0"

    # Tushare (请通过 .env 或环境变量设置 TUSHARE_TOKEN)
    tushare_token: str = ""

    # AkShare
    http_proxy: Optional[str] = ""
    https_proxy: Optional[str] = ""

    # Frontend
    nuxt_public_api_base: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# 确保 model_dir 为绝对路径（相对于此配置文件所在目录）
_config_dir = os.path.dirname(os.path.abspath(__file__))
if not settings.model_dir or not os.path.isabs(settings.model_dir):
    settings.model_dir = os.path.join(os.path.dirname(_config_dir), "models")
