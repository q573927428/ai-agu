"""
按日期批量拉取A股日行情 — 从Tushare Pro拉取写入MySQL

核心思路：
  Tushare daily 接口支持按 trade_date 一次性拉取全市场数据（最多6000条/次），
  比按单只股票拉取快 5000 倍。

用法:
  python scripts/fetch_daily_batch.py                           # 今日最近交易日
  python scripts/fetch_daily_batch.py 2026-06-05                # 指定日期
  python scripts/fetch_daily_batch.py --history 30              # 最近30个交易日
  python scripts/fetch_daily_batch.py 2026-06-01 2026-06-05     # 日期区间
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from decimal import Decimal
from loguru import logger
from sqlalchemy import text, func

from app.utils.db_utils import SessionLocal, engine
from app.models.stock_daily import StockDaily
from app.models.stock import StockBasic
from app.models.base import Base
from app.utils.date_utils import is_trade_day, get_latest_trade_day

# ---------- Tushare Pro ----------
import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


# ---------- 辅助函数 ----------

def _safe_decimal(value, places=4):
    """安全转换为 Decimal """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return round(Decimal(str(float(value))), places)
    except (ValueError, TypeError, Exception):
        return None


def _safe_int(value, multiplier=1):
    """安全转换为 int """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return int(float(value) * multiplier)
    except (ValueError, TypeError, Exception):
        return None


def _extract_symbol(ts_code: str) -> str:
    """ts_code → 纯数字代码，如 000001.SZ → 000001"""
    return ts_code.split(".")[0]


def ensure_tables_exist():
    """确保数据表已创建"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")


def upsert_batch_daily(records: list):
    """
    批量 INSERT ... ON DUPLICATE KEY UPDATE
    
    records: list[StockDaily]
    """
    if not records:
        return 0

    session = SessionLocal()
    try:
        # 分批写入，每批 2000 条（避免 SQL 参数过多）
        chunk_size = 2000
        MAX_SQL_PARAMS = 500
        chunk_size = min(chunk_size, MAX_SQL_PARAMS // 11)

        total = 0
        for chunk_start in range(0, len(records), chunk_size):
            chunk = records[chunk_start:chunk_start + chunk_size]

            value_clauses = []
            params = {}
            for i, rec in enumerate(chunk):
                suffix = f"_{i}"
                value_clauses.append(
                    f"(:stock_code{suffix}, :trade_date{suffix}, :open{suffix}, :high{suffix}, "
                    f":low{suffix}, :close{suffix}, :pre_close{suffix}, :change_val{suffix}, "
                    f":pct_chg{suffix}, :volume{suffix}, :amount{suffix})"
                )
                params.update({
                    f"stock_code{suffix}": rec.stock_code,
                    f"trade_date{suffix}": rec.trade_date,
                    f"open{suffix}": rec.open,
                    f"high{suffix}": rec.high,
                    f"low{suffix}": rec.low,
                    f"close{suffix}": rec.close,
                    f"pre_close{suffix}": rec.pre_close,
                    f"change_val{suffix}": rec.change,
                    f"pct_chg{suffix}": rec.pct_chg,
                    f"volume{suffix}": rec.volume,
                    f"amount{suffix}": rec.amount,
                })

            values_str = ",\n".join(value_clauses)
            stmt = text(f"""
                INSERT INTO stock_daily (stock_code, trade_date, open, high, low, close, pre_close, `change`, pct_chg, volume, amount)
                VALUES {values_str}
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    pre_close = VALUES(pre_close),
                    `change` = VALUES(`change`),
                    pct_chg = VALUES(pct_chg),
                    volume = VALUES(volume),
                    amount = VALUES(amount)
            """)
            session.execute(stmt, params)
            session.commit()
            total += len(chunk)

        return total
    except Exception as e:
        session.rollback()
        logger.error(f"批量写入失败: {e}")
        # 逐条回退
        success = 0
        for rec in chunk:
            try:
                stmt = text("""
                    INSERT INTO stock_daily (stock_code, trade_date, open, high, low, close, pre_close, `change`, pct_chg, volume, amount)
                    VALUES (:stock_code, :trade_date, :open, :high, :low, :close, :pre_close, :change_val, :pct_chg, :volume, :amount)
                    ON DUPLICATE KEY UPDATE
                        open = VALUES(open), high = VALUES(high), low = VALUES(low),
                        close = VALUES(close), pre_close = VALUES(pre_close),
                        `change` = VALUES(`change`), pct_chg = VALUES(pct_chg),
                        volume = VALUES(volume), amount = VALUES(amount)
                """)
                session.execute(stmt, {
                    "stock_code": rec.stock_code,
                    "trade_date": rec.trade_date,
                    "open": rec.open,
                    "high": rec.high,
                    "low": rec.low,
                    "close": rec.close,
                    "pre_close": rec.pre_close,
                    "change_val": rec.change,
                    "pct_chg": rec.pct_chg,
                    "volume": rec.volume,
                    "amount": rec.amount,
                })
                session.commit()
                success += 1
            except Exception as ind_e:
                session.rollback()
                logger.warning(f"  跳过 {rec.stock_code} {rec.trade_date}: {ind_e}")
        return success
    finally:
        session.close()


def fetch_one_day(trade_date_str: str, delay: float = 0.3) -> int:
    """
    拉取指定交易日全市场行情

    Args:
        trade_date_str: 日期 YYYY-MM-DD 或 YYYYMMDD
        delay: 请求间隔秒数

    Returns:
        int: 写入记录数
    """
    # 标准化日期格式
    trade_date_clean = trade_date_str.replace("-", "")
    trade_date_obj = datetime.strptime(trade_date_clean, "%Y%m%d").date()

    logger.info(f"📅 拉取 {trade_date_obj} 全市场日行情...")

    # 调用 pro.daily(trade_date=...) — 1次请求拉全市场
    time.sleep(delay)  # 限速
    try:
        df = pro.daily(trade_date=trade_date_clean)
    except Exception as e:
        logger.error(f"  ❌ 请求失败: {e}")
        return 0

    if df is None or df.empty:
        logger.warning(f"  ⚠️ {trade_date_obj} 无数据（非交易日或数据尚未入库）")
        return 0

    logger.info(f"  📥 获取到 {len(df)} 条记录")

    # 转换为 StockDaily 对象
    records = []
    for _, row in df.iterrows():
        ts_code = str(row.get("ts_code", "")).strip()
        if not ts_code:
            continue

        stock_code = _extract_symbol(ts_code)

        record = StockDaily(
            stock_code=stock_code,
            trade_date=trade_date_obj,
            open=_safe_decimal(row.get("open"), 3),
            high=_safe_decimal(row.get("high"), 3),
            low=_safe_decimal(row.get("low"), 3),
            close=_safe_decimal(row.get("close"), 3),
            pre_close=_safe_decimal(row.get("pre_close"), 3),
            change=_safe_decimal(row.get("change"), 3),
            pct_chg=_safe_decimal(row.get("pct_chg"), 6),
            volume=_safe_int(row.get("vol"), multiplier=100),       # 手 → 股
            amount=_safe_decimal(row.get("amount"), 2),             # 千元
        )
        # amount 千元 → 元
        if record.amount is not None:
            record.amount = _safe_decimal(float(record.amount) * 1000, 2)

        records.append(record)

    # 批量写入
    written = upsert_batch_daily(records)
    logger.info(f"  ✅ {trade_date_obj} 写入完成: {written}/{len(records)} 条")
    return written


def sync_stock_basic_snapshot(trade_date_obj: date):
    """将指定交易日的最新收盘价和涨跌幅同步到 stock_basic 表（仅当该日期是最新交易日时）"""
    session = SessionLocal()
    try:
        # 查询该日期是否是这个股票的最新交易日
        latest_sub = (
            session.query(
                StockDaily.stock_code,
                func.max(StockDaily.trade_date).label("max_date")
            )
            .filter(StockDaily.trade_date <= trade_date_obj)
            .group_by(StockDaily.stock_code)
            .subquery()
        )
        rows = (
            session.query(
                StockDaily.stock_code,
                StockDaily.trade_date,
                StockDaily.close,
                StockDaily.pct_chg,
            )
            .join(
                latest_sub,
                (StockDaily.stock_code == latest_sub.c.stock_code)
                & (StockDaily.trade_date == latest_sub.c.max_date)
            )
            .all()
        )

        updated = 0
        for r in rows:
            result = session.query(StockBasic).filter(StockBasic.stock_code == r.stock_code).update({
                "trade_date": r.trade_date,
                "close_price": r.close,
                "pct_chg": r.pct_chg,
            })
            if result:
                updated += 1

        session.commit()
        if updated > 0:
            logger.info(f"  ✅ stock_basic 快照更新: {updated} 只股票")
        return updated
    except Exception as e:
        session.rollback()
        logger.warning(f"  ⚠️ stock_basic 快照同步失败: {e}")
        return 0
    finally:
        session.close()


def get_trade_dates(start_date: date, end_date: date) -> list:
    """获取日期区间内的交易日列表"""
    trade_dates = []
    current = start_date
    while current <= end_date:
        if is_trade_day(current):
            trade_dates.append(current)
        current += timedelta(days=1)
    return trade_dates


def parse_args():
    parser = argparse.ArgumentParser(
        description="按日期批量拉取A股日行情（比按股票拉快 5000 倍）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/fetch_daily_batch.py
  python scripts/fetch_daily_batch.py 2026-06-05
  python scripts/fetch_daily_batch.py --history 30
  python scripts/fetch_daily_batch.py 2026-06-01 2026-06-05
  python scripts/fetch_daily_batch.py --delay 0.5
        """,
    )
    parser.add_argument("dates", nargs="*", help="日期范围：可指定1个或2个日期 (YYYY-MM-DD)")
    parser.add_argument("--history", type=int, default=0, help="拉取最近N个交易日历史数据")
    parser.add_argument("--delay", type=float, default=0.3, help="每次请求间隔秒数（默认0.3，Tushare免费版500次/分钟）")
    return parser.parse_args()


def main():
    args = parse_args()

    ensure_tables_exist()

    # 确定要拉取的交易日列表
    if args.history > 0:
        # --history N: 最近 N 个交易日
        today = datetime.now()
        dates = []
        current = today
        while len(dates) < args.history:
            if is_trade_day(current):
                dates.append(current.date())
            current -= timedelta(days=1)
        dates.reverse()
        logger.info(f"📋 将拉取最近 {len(dates)} 个交易日: {dates[0]} ~ {dates[-1]}")
    elif len(args.dates) == 2:
        # 日期区间
        start = datetime.strptime(args.dates[0], "%Y-%m-%d").date()
        end = datetime.strptime(args.dates[1], "%Y-%m-%d").date()
        dates = get_trade_dates(start, end)
        logger.info(f"📋 日期区间 {start} ~ {end}: {len(dates)} 个交易日")
    elif len(args.dates) == 1:
        # 指定单日
        d = datetime.strptime(args.dates[0], "%Y-%m-%d").date()
        dates = [d]
        logger.info(f"📋 单日: {d}")
    else:
        # 默认：最近交易日
        latest = get_latest_trade_day()
        dates = [latest.date()]
        logger.info(f"📋 默认最近交易日: {dates[0]}")

    if not dates:
        logger.warning("⚠️ 没有交易日需要拉取")
        return

    # 逐日拉取（每天1次 pro.daily(trade_date=...)）
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 开始按日期批量拉取日行情  ({len(dates)} 个交易日)")
    logger.info(f"{'='*60}")

    total_written = 0
    start_time = time.time()

    for i, trade_date in enumerate(dates):
        date_str = trade_date.strftime("%Y%m%d")
        written = fetch_one_day(date_str, delay=args.delay)
        total_written += written

        # 进度
        elapsed = time.time() - start_time
        pct = (i + 1) / len(dates) * 100
        logger.info(f"  📊 进度: {i+1}/{len(dates)} ({pct:.1f}%) | 已写入 {total_written} 条 | 耗时 {elapsed:.1f}s")

    # 同步最新交易日数据到 stock_basic 快照字段
    if dates:
        latest_date = max(dates)
        logger.info(f"📸 同步最新交易日 {latest_date} 行情到 stock_basic 快照字段...")
        sync_stock_basic_snapshot(latest_date)

    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 全部完成！")
    logger.info(f"  交易日: {len(dates)} 天")
    logger.info(f"  写入记录: {total_written} 条")
    logger.info(f"  总耗时: {elapsed:.1f} 秒")
    logger.info(f"  日均耗时: {elapsed/max(len(dates),1):.2f} 秒/天")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()