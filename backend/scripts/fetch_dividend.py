"""
拉取分红送股数据 — 从 Tushare Pro dividend 接口拉取

用法:
  python scripts/fetch_dividend.py                       # 全量拉取（按日期轮询）
  python scripts/fetch_dividend.py 000001                 # 拉取单只股票
  python scripts/fetch_dividend.py --incremental          # 增量拉取
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime, date, timedelta
from decimal import Decimal
from loguru import logger
from sqlalchemy import text, func

from app.utils.db_utils import SessionLocal, engine
from app.models.stock import StockBasic
from app.models.stock_event import StockEvent
from app.models.base import Base

# ---------- Tushare Pro ----------
import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def ensure_tables_exist():
    """确保数据表已创建"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")


def _safe_decimal(value, places=4):
    if value is None or (isinstance(value, float) and (value != value)):
        return None
    try:
        return round(Decimal(str(float(value))), places)
    except (ValueError, TypeError, Exception):
        return None


def _safe_float(value) -> float:
    if value is None or (isinstance(value, float) and (value != value)):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_str(value) -> str:
    if value is None or (isinstance(value, float) and (value != value)):
        return ""
    return str(value).strip()


def _safe_date(value):
    if value is None or (isinstance(value, float) and (value != value)):
        return None
    s = _safe_str(value)
    if not s:
        return None
    try:
        s = s.replace("-", "")
        if len(s) == 8:
            return datetime.strptime(s, "%Y%m%d").date()
    except (ValueError, TypeError):
        pass
    return None


def _extract_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0]


def build_description(row) -> str:
    parts = []
    stk_bo = _safe_float(row.get("stk_bo_rate", 0))
    stk_co = _safe_float(row.get("stk_co_rate", 0))
    cash = _safe_float(row.get("cash_div", 0))

    if stk_bo >= 0.001:
        parts.append(f"送{int(round(stk_bo * 10))}")
    if stk_co >= 0.001:
        parts.append(f"转{int(round(stk_co * 10))}")
    if cash >= 0.01:
        parts.append(f"派{cash:.2f}")

    return "".join(parts) if parts else "仅分红"


def determine_event_type(row) -> str:
    stk_bo = _safe_float(row.get("stk_bo_rate", 0))
    stk_co = _safe_float(row.get("stk_co_rate", 0))
    cash = _safe_float(row.get("cash_div", 0))
    stk_div = _safe_float(row.get("stk_div", 0))

    if stk_div > 0 and cash > 0:
        return "mixed"
    elif stk_div > 0:
        return "split_bonus"
    elif cash > 0:
        return "cash_dividend"
    return "unknown"


def fetch_stock_dividend(ts_code: str, delay: float = 0.3) -> list:
    """
    拉取单只股票的分红送股记录（用于单只股票查询，非全量用）
    """
    time.sleep(delay)
    try:
        df = pro.dividend(ts_code=ts_code)
    except Exception as e:
        logger.error(f"  ❌ {ts_code} 请求失败: {e}")
        return []

    if df is None or df.empty:
        return []

    stock_code = _extract_symbol(ts_code)
    records = []

    for _, row in df.iterrows():
        ex_date = _safe_date(row.get("ex_date"))
        if not ex_date:
            continue

        div_proc = _safe_str(row.get("div_proc", ""))
        if div_proc not in ("实施",):
            continue

        desc = build_description(row)
        event_type = determine_event_type(row)

        record = StockEvent(
            stock_code=stock_code,
            ex_date=ex_date,
            event_type=event_type,
            description=desc,
            end_date=_safe_str(row.get("end_date", "")),
            ann_date=_safe_date(row.get("ann_date")),
            div_proc=div_proc,
            stk_div=_safe_decimal(row.get("stk_div")),
            stk_bo_rate=_safe_decimal(row.get("stk_bo_rate")),
            stk_co_rate=_safe_decimal(row.get("stk_co_rate")),
            cash_div=_safe_decimal(row.get("cash_div")),
            cash_div_tax=_safe_decimal(row.get("cash_div_tax")),
            record_date=_safe_date(row.get("record_date")),
            pay_date=_safe_date(row.get("pay_date")),
            div_listdate=_safe_date(row.get("div_listdate")),
            imp_ann_date=_safe_date(row.get("imp_ann_date")),
        )
        records.append(record)

    return records


def upsert_events(session, records: list) -> int:
    if not records:
        return 0

    total = 0
    for rec in records:
        try:
            existing = session.query(StockEvent).filter(
                StockEvent.stock_code == rec.stock_code,
                StockEvent.ex_date == rec.ex_date,
            ).first()
            if existing:
                for col in StockEvent.__table__.columns:
                    if col.name in ("id", "created_at"):
                        continue
                    val = getattr(rec, col.name)
                    if val is not None:
                        setattr(existing, col.name, val)
            else:
                session.add(rec)
            session.commit()
            total += 1
        except Exception as e:
            session.rollback()
            logger.warning(f"  跳过 {rec.stock_code} {rec.ex_date}: {e}")
    return total


def get_ts_code(stock_code: str) -> str:
    prefix = stock_code[:3]
    if prefix in {"000", "001", "002", "003", "300", "301"}:
        return f"{stock_code}.SZ"
    elif prefix in {"600", "601", "603", "605", "688", "689"}:
        return f"{stock_code}.SH"
    else:
        return f"{stock_code}.BJ"


def fetch_dividend_by_imp_ann_date(target_date: date, delay: float = 0.3) -> list:
    """
    按实施公告日拉取全市场分红送股数据

    调用 pro.dividend(imp_ann_date='YYYYMMDD') 获取当天所有实施公告的分红数据，
    避免全量拉取后再在本地过滤，大幅减少请求量和数据传输。

    Args:
        target_date: 实施公告日期
        delay: 请求间隔秒数

    Returns:
        list[StockEvent]: 该实施公告日的分红事件列表
    """
    date_str = target_date.strftime("%Y%m%d")
    time.sleep(delay)
    try:
        df = pro.dividend(imp_ann_date=date_str)
    except Exception as e:
        logger.error(f"  ❌ {date_str} 请求失败: {e}")
        return []

    if df is None or df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        ex_date = _safe_date(row.get("ex_date"))
        if not ex_date:
            continue

        div_proc = _safe_str(row.get("div_proc", ""))
        if div_proc not in ("实施",):
            continue

        ts_code = _safe_str(row.get("ts_code", ""))
        if not ts_code:
            continue

        stock_code = _extract_symbol(ts_code)
        desc = build_description(row)
        event_type = determine_event_type(row)

        record = StockEvent(
            stock_code=stock_code,
            ex_date=ex_date,
            event_type=event_type,
            description=desc,
            end_date=_safe_str(row.get("end_date", "")),
            ann_date=_safe_date(row.get("ann_date")),
            div_proc=div_proc,
            stk_div=_safe_decimal(row.get("stk_div")),
            stk_bo_rate=_safe_decimal(row.get("stk_bo_rate")),
            stk_co_rate=_safe_decimal(row.get("stk_co_rate")),
            cash_div=_safe_decimal(row.get("cash_div")),
            cash_div_tax=_safe_decimal(row.get("cash_div_tax")),
            record_date=_safe_date(row.get("record_date")),
            pay_date=_safe_date(row.get("pay_date")),
            div_listdate=_safe_date(row.get("div_listdate")),
            imp_ann_date=_safe_date(row.get("imp_ann_date")),
        )
        records.append(record)

    return records


def fetch_dividend_incremental(session=None, batch_size: int = 500, delay: float = 0.3) -> int:
    """
    增量拉取/全量拉取 — 按 imp_ann_date 逐日轮询（统一入口）

    判断逻辑（自动判断全量或增量）：
      - 库中无数据（imp_ann_date 为 NULL）→ 全量：从 2000-01-01 到今天
      - 库中最新的 imp_ann_date >= 今天 → 已最新，跳过
      - 否则 → 增量：从 latest_imp_ann_date + 1 到今天

    全量和增量完全共用同一套日期轮询逻辑，仅起始日期不同。

    Args:
        session: 可复用外部 session，None 则内部创建
        batch_size: 保留参数（兼容性）
        delay: 请求间隔秒数

    Returns:
        int: 写入的记录数
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        latest_imp_ann_date = session.query(func.max(StockEvent.imp_ann_date)).scalar()
        today = date.today()

        # ---- 确定日期范围 ----
        if latest_imp_ann_date is None:
            # 全量：从未拉取过
            start_date = date(2000, 1, 1)
            end_date = today
            total_days = (end_date - start_date).days + 1
            logger.info(f"📋 全量模式：从 {start_date} 到 {end_date}（预计 {total_days} 天），逐日拉取")
        elif latest_imp_ann_date >= today:
            logger.info(f"⏭️ 库中最新实施公告日 {latest_imp_ann_date} >= 今日 {today}，跳过拉取")
            return 0
        else:
            # 增量：从最新日期的下一天开始
            start_date = latest_imp_ann_date + timedelta(days=1)
            end_date = today
            logger.info(f"📋 增量模式：库内最新实施公告日 {latest_imp_ann_date}，轮询日期 {start_date} ~ {end_date}")

        # ---- 执行逐天轮询 ----
        total_records = 0
        total_dates = 0
        loop_start = time.time()
        current_date = start_date

        while current_date <= end_date:
            logger.info(f"📅 拉取实施公告日 {current_date} 的数据...")
            records = fetch_dividend_by_imp_ann_date(current_date, delay=delay)
            if records:
                written = upsert_events(session, records)
                total_records += written
                total_dates += 1
                logger.info(f"  ✅ {current_date}: 写入 {written} 条")
            else:
                logger.info(f"  ℹ️ {current_date}: 无数据")

            elapsed = time.time() - loop_start
            days_elapsed = (current_date - start_date).days + 1
            total_days_plan = (end_date - start_date).days + 1
            if days_elapsed % 10 == 0 or current_date == end_date:
                logger.info(f"   进度 {days_elapsed}/{total_days_plan} 天 | 已写入 {total_records} 条 | 耗时 {elapsed:.1f}s")

            current_date += timedelta(days=1)

        elapsed = time.time() - loop_start
        logger.info(f"\n🎉 拉取完成！")
        logger.info(f"  涉及日期: {total_dates} 天")
        logger.info(f"  写入事件数: {total_records} 条")
        logger.info(f"  总耗时: {elapsed:.1f}s")
        return total_records

    finally:
        if close_session:
            session.close()


def fetch_single_stock(code: str, delay: float = 0.3):
    """拉取单只股票的分红送股数据"""
    session = SessionLocal()
    try:
        code_padded = code.zfill(6)
        stock = session.query(StockBasic).filter(StockBasic.stock_code == code_padded).first()
        if not stock:
            stock = session.query(StockBasic).filter(StockBasic.stock_code == code).first()

        if stock:
            ts_code_full = stock.ts_code if hasattr(stock, 'ts_code') and stock.ts_code else (
                f"{stock.stock_code}.SZ" if stock.stock_code.startswith(("0", "3")) else f"{stock.stock_code}.SH"
            )
        else:
            ts_code_full = f"{code_padded}.SZ" if code_padded.startswith(("0", "3")) else f"{code_padded}.SH"

        logger.info(f"📋 拉取 {ts_code_full} 分红送股数据...")
        records = fetch_stock_dividend(ts_code_full, delay=delay)
        if records:
            written = upsert_events(session, records)
            logger.info(f"✅ 写入 {written} 条")
        else:
            logger.info("⚠️ 无数据")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="拉取分红送股数据")
    parser.add_argument("stock_code", nargs="?", default=None, help="股票代码（可选，不传则全量拉取）")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数")
    parser.add_argument("--incremental", action="store_true", help="增量拉取（按最新 imp_ann_date）")
    parser.add_argument("--batch", type=int, default=500, help="已废弃，仅保持兼容")
    args = parser.parse_args()

    ensure_tables_exist()

    if args.incremental:
        fetch_dividend_incremental(delay=args.delay)
    elif args.stock_code:
        fetch_single_stock(args.stock_code, delay=args.delay)
    else:
        fetch_dividend_incremental(delay=args.delay)


if __name__ == "__main__":
    main()