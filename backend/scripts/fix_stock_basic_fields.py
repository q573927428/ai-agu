"""
补充 stock_basic 表中缺失字段的脚本
(fullname, enname, exchange, curr_type, delist_date, is_hs)

问题原因：fetch_real_data.py 中调用 pro.stock_basic() 时
未指定 fields 参数，Tushare 默认只返回部分字段
(ts_code, symbol, name, area, industry, cnspell, market, list_date, act_name, act_ent_type)
导致 fullname/enname/exchange 等字段未获取到，全部写入 NULL。

用法:
  python scripts/fix_stock_basic_fields.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.utils.db_utils import SessionLocal
from app.models.stock import StockBasic

# ---------- Tushare Pro ----------
import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def fix_stock_basic_fields():
    """从 Tushare 重新拉取完整字段并 UPDATE stock_basic 表"""
    db = SessionLocal()
    try:
        logger.info("🚀 开始从 Tushare 拉取完整 stock_basic 字段...")

        # 显式指定所有需要的字段
        df = pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,'
                   'market,exchange,curr_type,list_status,list_date,delist_date,'
                   'is_hs,act_name,act_ent_type'
        )

        if df is None or df.empty:
            logger.error("❌ Tushare 返回为空")
            return

        logger.info(f"📊 从 Tushare 获取到 {len(df)} 条股票数据")

        update_count = 0
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            symbol = str(row.get("symbol", "")).strip()
            if not ts_code:
                continue

            code = symbol or ts_code.split(".")[0]

            # 查找数据库中已有的记录
            existing = db.query(StockBasic).filter(StockBasic.stock_code == code).first()
            if not existing:
                continue

            need_update = False

            # 要补充的字段列表
            field_mapping = {
                "fullname": "fullname",
                "enname": "enname",
                "exchange": "exchange",
                "curr_type": "curr_type",
                "delist_date": "delist_date",
                "is_hs": "is_hs",
            }

            for tushare_field, db_field in field_mapping.items():
                val = row.get(tushare_field)
                if val is not None and str(val).strip() and str(val).strip() != "nan":
                    str_val = str(val).strip()
                    # 特殊处理 delist_date 日期格式转换 YYYYMMDD → date
                    if db_field == "delist_date" and len(str_val) == 8 and str_val.isdigit():
                        try:
                            date_val = datetime.strptime(str_val, "%Y%m%d").date()
                            if getattr(existing, db_field) != date_val:
                                setattr(existing, db_field, date_val)
                                need_update = True
                        except ValueError:
                            pass
                    else:
                        if getattr(existing, db_field) != str_val:
                            setattr(existing, db_field, str_val)
                            need_update = True

            if need_update:
                update_count += 1

        db.commit()
        logger.info(f"✅ 更新完成：共更新 {update_count} 条记录")

        # 验证结果
        null_counts = db.query(
            db.query(StockBasic).filter(StockBasic.fullname.is_(None)).count().label("fullname_null"),
            db.query(StockBasic).filter(StockBasic.enname.is_(None)).count().label("enname_null"),
            db.query(StockBasic).filter(StockBasic.exchange.is_(None)).count().label("exchange_null"),
            db.query(StockBasic).filter(StockBasic.curr_type.is_(None)).count().label("curr_type_null"),
            db.query(StockBasic).filter(StockBasic.is_hs.is_(None)).count().label("is_hs_null"),
        ).first()
        if null_counts:
            logger.info(f"📊 验证结果（剩余 NULL 数）：")
            logger.info(f"  fullname: {null_counts.fullname_null}")
            logger.info(f"  enname: {null_counts.enname_null}")
            logger.info(f"  exchange: {null_counts.exchange_null}")
            logger.info(f"  curr_type: {null_counts.curr_type_null}")
            logger.info(f"  is_hs: {null_counts.is_hs_null}")

    except Exception as e:
        logger.error(f"❌ 补充字段失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_stock_basic_fields()