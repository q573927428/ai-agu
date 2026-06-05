"""应用配置管理"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MySQL
    mysql_root_password: str = "root123"
    mysql_password: str = "agu123"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "agu_quant"

    # Backend
    database_url: str = "mysql+pymysql://agu_user:agu123@localhost:3306/agu_quant"
    app_env: str = "development"
    log_level: str = "INFO"

    # Model
    model_dir: str = "./models"
    model_version: str = "v1.0"

    # AkShare
    http_proxy: Optional[str] = ""
    https_proxy: Optional[str] = ""

    # Frontend
    nuxt_public_api_base: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()