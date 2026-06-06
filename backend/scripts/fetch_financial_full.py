"""
全量拉取上市公司历史财务数据脚本

拉取所有股票的全部历史时间财务数据到 4 张表：
  - income （利润表）
  - balancesheet（资产负债表）
  - cashflow（现金流量表）
  - fina_indicator（财务指标）

用法:
  python scripts/fetch_financial_full.py                        # 全量拉取
  python scripts/fetch_financial_full.py --top 100              # 拉取前100只（测试用）
  python scripts/fetch_financial_full.py --delay 0.5            # 调整请求间隔
  python scripts/fetch_financial_full.py --resume               # 断点续传（跳过已有最多数据的表）
  python scripts/fetch_financial_full.py --checkpoint           # 仅检查各表数据量，不拉取
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.utils.db_utils import SessionLocal, engine
from app.models.base import Base
from app.models.stock import StockBasic
from app.models.income import Income
from app.models.balancesheet import Balancesheet
from app.models.cashflow import Cashflow
from app.models.fina_indicator import FinaIndicator

# ---------- Tushare Pro 初始化 ----------
import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# ---------- 简易限速 ----------
LAST_REQUEST_TIME = 0
REQUEST_LOCK = None  # 单线程不需要锁


def _rate_limit(min_interval: float = 0.35) -> None:
    """简易速率限制"""
    global LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    LAST_REQUEST_TIME = time.time()


def parse_args():
    parser = argparse.ArgumentParser(description="全量拉取上市公司历史财务数据到MySQL")
    parser.add_argument("--top", type=int, default=0, help="限制股票数量 (0=全部)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="每次请求间隔秒数 (默认0.5，Tushare免费版500次/分钟)")
    parser.add_argument("--resume", action="store_true",
                        help="断点续传模式：跳过已有数据的股票，仅拉取缺失的部分")
    parser.add_argument("--checkpoint", action="store_true",
                        help="检查模式：仅显示各表数据量，不拉取数据")
    parser.add_argument("--skip-tables", nargs="*", default=[],
                        help="跳过的表名，如 --skip-tables cashflow")
    return parser.parse_args()


def check_tables(db: Session) -> dict:
    """检查4张财务表的数据量统计"""
    stats = {}
    tables_info = [
        ("income", Income, "利润表"),
        ("balancesheet", Balancesheet, "资产负债表"),
        ("cashflow", Cashflow, "现金流量表"),
        ("fina_indicator", FinaIndicator, "财务指标"),
    ]
    for table_name, model_cls, label in tables_info:
        count = db.query(model_cls).count()
        # 获取最早和最晚日期
        row = db.execute(
            text(f"SELECT MIN(end_date), MAX(end_date) FROM `{table_name}`")
        ).fetchone()
        min_date, max_date = row if row else (None, None)
        stats[table_name] = {
            "label": label,
            "count": count,
            "min_date": str(min_date) if min_date else "N/A",
            "max_date": str(max_date) if max_date else "N/A",
        }
        logger.info(f"  {label} ({table_name}): {count} 条"
                     f" ({min_date or 'N/A'} ~ {max_date or 'N/A'})")
    return stats


def get_existing_stocks(db: Session, table_name: str) -> set:
    """获取某表中已有哪些股票代码（用于断点续传）"""
    rows = db.execute(
        text(f"SELECT DISTINCT stock_code FROM `{table_name}`")
    ).fetchall()
    return {row[0] for row in rows}


def _safe_date_str(val) -> str | None:
    if val is None or (isinstance(val, float) and __import__('numpy').isnan(val)):
        return None
    s = str(val).strip()
    if not s or s == "nan":
        return None
    try:
        if len(s) == 8 and s.isdigit():
            return datetime.strptime(s, "%Y%m%d").strftime("%Y-%m-%d")
        return s
    except Exception:
        return None


def _financial_upsert(session: Session, table_model, records: list, unique_cols: list):
    """批量 upsert 财务数据"""
    if not records:
        return
    table_name = table_model.__tablename__
    for rec in records:
        try:
            cols = list(rec.keys())
            where_clause = " AND ".join([f"`{c}` = :{c}_uk" for c in unique_cols])
            uk_params = {f"{c}_uk": rec[c] for c in unique_cols}
            stmt_check = text(f"SELECT id FROM `{table_name}` WHERE {where_clause} LIMIT 1")
            result = session.execute(stmt_check, uk_params).fetchone()
            if result:
                set_clause = ", ".join([f"`{c}` = :{c}" for c in cols])
                stmt = text(f"UPDATE `{table_name}` SET {set_clause} WHERE id = :row_id")
                rec["row_id"] = result[0]
                session.execute(stmt, rec)
            else:
                col_names = ", ".join([f"`{c}`" for c in cols])
                val_placeholders = ", ".join([f":{c}" for c in cols])
                stmt = text(f"INSERT INTO `{table_name}` ({col_names}) VALUES ({val_placeholders})")
                session.execute(stmt, rec)
        except Exception as e:
            session.rollback()
            logger.warning(f"  ⚠️ upsert 跳过: {e}")
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"  ⚠️ 批量提交失败，逐条回退: {e}")
        for rec in records:
            try:
                cols = list(rec.keys())
                col_names = ", ".join([f"`{c}`" for c in cols])
                val_placeholders = ", ".join([f":{c}" for c in cols])
                on_dup = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in cols if c not in unique_cols + ["id"]])
                stmt = text(f"INSERT INTO `{table_name}` ({col_names}) VALUES ({val_placeholders}) "
                            f"ON DUPLICATE KEY UPDATE {on_dup}")
                session.execute(stmt, rec)
                session.commit()
            except Exception as ind_e:
                session.rollback()
                logger.warning(f"    ↪ 跳过: {ind_e}")


def fetch_table(db: Session, api_name: str, api_func, model_cls, table_name: str,
                unique_keys: list, stocks: list, delay: float, resume: bool) -> int:
    """拉取单个财务表的所有历史数据"""
    # 断点续传：获取已存在的股票代码
    existing_stocks = set()
    if resume:
        existing_stocks = get_existing_stocks(db, table_name)
        if existing_stocks:
            logger.info(f"    ↪ 断点续传: 已跳过 {len(existing_stocks)} 只已有数据的股票")

    total = len(stocks)
    all_records = []
    success_count = 0
    skip_count = 0
    error_count = 0
    progress_interval = max(1, total // 20)  # 每5%进度输出一次

    for idx, (stock_code, ts_code) in enumerate(stocks):
        # 断点续传检测
        if resume and stock_code in existing_stocks:
            skip_count += 1
            if idx % 500 == 0:
                logger.info(f"    [{idx}/{total}] 已跳过 {skip_count} 只（已有数据）")
            continue

        if idx % progress_interval == 0 and idx > 0:
            pct = idx * 100 // total
            logger.info(f"    [{idx}/{total}] {pct}% - {api_name}: {success_count} 成功, "
                         f"{error_count} 错误")

        _rate_limit(delay)
        try:
            # 调用 Tushare Pro 接口获取全部历史数据
            df = api_func(ts_code=ts_code)
        except Exception as e:
            err_msg = str(e)
            if "频率超限" in err_msg or "超限" in err_msg or "rate limit" in err_msg.lower():
                logger.warning(f"    ⚠️ [频率超限] 等待61s...")
                time.sleep(61)
                try:
                    df = api_func(ts_code=ts_code)
                except Exception as e2:
                    logger.warning(f"    ❌ {stock_code} {api_name} 重试仍失败: {e2}")
                    error_count += 1
                    continue
            else:
                logger.warning(f"    ⚠️ {stock_code} {api_name} 无数据: {e}")
                error_count += 1
                continue

        if df is None or df.empty:
            skip_count += 1
            continue

        for _, row in df.iterrows():
            end_date_str = _safe_date_str(row.get("end_date"))
            if not end_date_str:
                continue
            end_date_val = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            if api_name == "财务指标":
                rec = {"stock_code": stock_code, "end_date": end_date_val}
            else:
                report_type = 1
                try:
                    rt = row.get("report_type")
                    if rt is not None and not (isinstance(rt, float) and __import__('numpy').isnan(rt)):
                        report_type = int(rt)
                except Exception:
                    pass
                rec = {"stock_code": stock_code, "end_date": end_date_val, "report_type": report_type}

            # 字段映射（基于 Tushare Pro 实际返回列名）
            if api_name == "利润表":
                from scripts.fix_financial_mapping import INCOME_FIELD_MAP as field_map
            elif api_name == "资产负债表":
                from scripts.fix_financial_mapping import BALANCESHEET_FIELD_MAP as field_map
            elif api_name == "现金流量表":
                from scripts.fix_financial_mapping import CASHFLOW_FIELD_MAP as field_map
            elif api_name == "财务指标":
                from scripts.fix_financial_mapping import FINA_INDICATOR_FIELD_MAP as field_map
            else:
                field_map = {}

            # 只写入目标表实际存在的字段
            model_columns = {col.name for col in model_cls.__table__.columns}
            for src_col, dst_col in field_map.items():
                if dst_col not in model_columns:
                    continue
                if src_col in row.index:
                    val = row.get(src_col)
                    if val is not None and not (isinstance(val, float) and __import__('numpy').isnan(val)):
                        rec[dst_col] = float(val)

            all_records.append(rec)
            success_count += 1

        if len(all_records) >= 500:
            _financial_upsert(db, model_cls, all_records, unique_keys)
            all_records = []

    if all_records:
        _financial_upsert(db, model_cls, all_records, unique_keys)

    total_in_db = db.query(model_cls).count()
    logger.info(f"    ✅ {api_name} 完成: {success_count} 条新增, "
                 f"跳过 {skip_count}, 错误 {error_count}, 库内总计 {total_in_db}")
    return success_count


def main():
    args = parse_args()

    # 确保表存在
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")

    db = SessionLocal()
    try:
        # 先检查当前数据量
        logger.info(f"\n{'='*50}")
        logger.info("📊 当前财务数据统计")
        logger.info(f"{'='*50}")
        stats = check_tables(db)

        if args.checkpoint:
            logger.info("\n✅ 检查完成（--checkpoint 模式，未拉取数据）")
            return

        # 获取所有股票
        stocks = db.query(StockBasic.stock_code, StockBasic.ts_code).all()
        if args.top > 0:
            stocks = stocks[:args.top]
        total = len(stocks)
        logger.info(f"\n📊 将拉取 {total} 只股票的全量历史财务数据...")

        # 4张表的配置
        api_configs = [
            ("利润表", pro.income, Income, "income", ["stock_code", "end_date", "report_type"]),
            ("资产负债表", pro.balancesheet, Balancesheet, "balancesheet", ["stock_code", "end_date", "report_type"]),
            ("现金流量表", pro.cashflow, Cashflow, "cashflow", ["stock_code", "end_date", "report_type"]),
            ("财务指标", pro.fina_indicator, FinaIndicator, "fina_indicator", ["stock_code", "end_date"]),
        ]

        start_time = time.time()
        total_all = 0

        for api_name, api_func, model_cls, table_name, unique_keys in api_configs:
            if table_name in args.skip_tables:
                logger.info(f"⏭️ 跳过 {api_name} ({table_name}) --skip-tables 指定")
                continue

            # 断点续传：如果该表已有数据且未指定 --resume，询问式提示
            if stats[table_name]["count"] > 0 and not args.resume:
                logger.info(f"\n  ── {api_name} ({table_name}) 已有 {stats[table_name]['count']} 条数据 ──")
                logger.info(f"     ↪ 如需断点续传请加 --resume 参数，否则将继续全量拉取（已有记录会跳过）")
            else:
                logger.info(f"\n  ── 拉取 {api_name} ({table_name}) ──")

            table_start = time.time()
            count = fetch_table(
                db=db,
                api_name=api_name,
                api_func=api_func,
                model_cls=model_cls,
                table_name=table_name,
                unique_keys=unique_keys,
                stocks=stocks,
                delay=args.delay,
                resume=args.resume and stats[table_name]["count"] > 0,
            )
            elapsed = time.time() - table_start
            total_all += count
            speed = count / elapsed if elapsed > 0 else 0
            logger.info(f"     ⏱ 耗时: {elapsed:.1f}s, 速度: {speed:.1f} 条/s")

        # 最终统计
        total_elapsed = time.time() - start_time
        logger.info(f"\n{'='*50}")
        logger.info("📊 全量财务数据拉取完成统计")
        logger.info(f"{'='*50}")
        logger.info(f"  总耗时: {total_elapsed:.1f}s ({total_elapsed/60:.1f}分钟)")
        logger.info(f"  总新增: {total_all} 条")
        check_tables(db)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断")
        logger.info("💡 下次可加 --resume 参数断点续传")
    except Exception as e:
        logger.error(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()