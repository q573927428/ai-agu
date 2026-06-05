"""数据库初始化脚本"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings


def init_database():
    """创建数据库和数据表"""
    engine = create_engine(
        f"mysql+pymysql://root:{settings.mysql_root_password}@{settings.mysql_host}:{settings.mysql_port}",
        echo=True,
    )

    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.execute(text(f"CREATE USER IF NOT EXISTS 'agu_user'@'%' IDENTIFIED BY '{settings.mysql_password}'"))
        conn.execute(text(f"GRANT ALL PRIVILEGES ON `{settings.mysql_database}`.* TO 'agu_user'@'%'"))
        conn.execute(text("FLUSH PRIVILEGES"))
        conn.commit()

    print(f"数据库 {settings.mysql_database} 创建成功!")


def create_tables():
    """创建所有数据表"""
    from app.models import Base

    engine = create_engine(settings.database_url, echo=True)
    Base.metadata.create_all(bind=engine)
    print("所有数据表创建成功!")


if __name__ == "__main__":
    init_database()
    create_tables()