"""
拉取分红送股数据 — 从 Tushare Pro dividend 接口拉取

用法:
  python scripts/fetch_dividend.py                       # 拉取全市场所有股票
  python scripts/fetch_dividend.py 000001                 # 拉取单只股票
  python scripts/fetch_dividend.py --batch 500            # 分批拉取，每批N只
  python scripts/fetch_dividend.py --incremental          # 增量拉取（按最新 ann_date）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime
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
    if value is None or (isinstance(value, float) and (value != value)):  # NaN check
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
    """尝试将 YYYYMMDD 或 YYYY-MM-DD 转为 date 对象"""
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
    """ts_code → 纯数字代码"""
    return ts_code.split(".")[0]


def build_description(row) -> str:
    """构建描述文字，如 10送5转3派1.2"""
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
    """判断事件类型"""
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
    拉取单只股票的分红送股记录
    Returns: list[StockEvent]
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
            continue  # 没有除权除息日的记录跳过

        div_proc = _safe_str(row.get("div_proc", ""))
        if div_proc not in ("实施",):
            continue  # 只取已实施的记录

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
    """批量写入事件表（去重）"""
    if not records:
        return 0

    total = 0
    for rec in records:
        try:
            # 检查是否已存在
            existing = session.query(StockEvent).filter(
                StockEvent.stock_code == rec.stock_code,
                StockEvent.ex_date == rec.ex_date,
            ).first()
            if existing:
                # 更新
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
    """根据股票代码前3位判断交易所后缀"""
    prefix = stock_code[:3]
    if prefix in {"000", "001", "002", "003", "300", "301"}:
        return f"{stock_code}.SZ"
    elif prefix in {"600", "601", "603", "605", "688", "689"}:
        return f"{stock_code}.SH"
    else:
        return f"{stock_code}.BJ"


def fetch_all_stocks(batch_size: int = 500, delay: float = 0.3):
    """拉取全市场所有股票的分红送股数据"""
    session = SessionLocal()
    try:
        # 获取所有股票
        stocks = session.query(StockBasic.stock_code).all()
        stock_codes = [s[0] for s in stocks]
        logger.info(f"📋 共 {len(stock_codes)} 只股票待处理")

        # 分批处理
        total_records = 0
        total_stocks = 0
        start_time = time.time()

        for batch_start in range(0, len(stock_codes), batch_size):
            batch = stock_codes[batch_start:batch_start + batch_size]
            batch_records = 0

            logger.info(f"📦 第 {batch_start // batch_size + 1} 批 ({len(batch)} 只)")

            for i, code in enumerate(batch):
                ts_code_full = get_ts_code(code)
                records = fetch_stock_dividend(ts_code_full, delay=delay)
                if records:
                    written = upsert_events(session, records)
                    batch_records += written
                    total_records += written
                    total_stocks += 1

                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"   进度 {batch_start + i + 1}/{len(stock_codes)} | 已获取 {total_records} 条 | 耗时 {elapsed:.1f}s")

            logger.info(f"  ✅ 本批完成: {batch_records} 条")

        elapsed = time.time() - start_time
        logger.info(f"\n🎉 全部完成！")
        logger.info(f"  有事件股票: {total_stocks} 只")
        logger.info(f"  总事件数: {total_records} 条")
        logger.info(f"  总耗时: {elapsed:.1f}s")
    finally:
        session.close()


def fetch_single_stock(code: str, delay: float = 0.3):
    """拉取单只股票的分红送股数据"""
    session = SessionLocal()
    try:
        # 确定 ts_code
        code_padded = code.zfill(6)
        stock = session.query(StockBasic).filter(StockBasic.stock_code == code_padded).first()
        if not stock:
            # 尝试原样查询
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


def fetch_dividend_incremental(session=None, batch_size: int = 500, delay: float = 0.3) -> int:
    """
    增量拉取分红送股数据

    判断逻辑：
      查询 stock_event 表的最大 imp_ann_date（实施公告日）
      - 如果为 NULL → 从未拉取过 → 调用全量拉取 fetch_all_stocks()
      - 如果不为 NULL → 已有数据，遍历全市场股票
        → 每只调用 pro.dividend(ts_code=...)
        → 只保留 imp_ann_date >= latest_imp_ann_date 的记录
        → upsert 写入（已有去重逻辑）

    Args:
        session: 可复用外部 session，None 则内部创建
        batch_size: 每批股票数
        delay: 请求间隔秒数

    Returns:
        int: 写入的记录数
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        # 查询库中最新的 imp_ann_date
        latest_imp_ann_date = session.query(func.max(StockEvent.imp_ann_date)).scalar()

        if latest_imp_ann_date is None:
            logger.info("📋 数据库无分红数据，执行全量拉取...")
            fetch_all_stocks(batch_size=batch_size, delay=delay)
            total = session.query(StockEvent).count()
            logger.info(f"✅ 全量拉取完成，共 {total} 条记录")
            return total

        logger.info(f"📋 增量模式：库内最新实施公告日 {latest_imp_ann_date}，拉取此后新数据")

        # 获取所有股票
        stocks = session.query(StockBasic.stock_code).all()
        stock_codes = [s[0] for s in stocks]
        logger.info(f"📋 共 {len(stock_codes)} 只股票待处理")

        total_records = 0
        total_stocks = 0
        start_time = time.time()

        for batch_start in range(0, len(stock_codes), batch_size):
            batch = stock_codes[batch_start:batch_start + batch_size]
            batch_records = 0

            logger.info(f"📦 第 {batch_start // batch_size + 1} 批 ({len(batch)} 只)")

            for i, code in enumerate(batch):
                ts_code_full = get_ts_code(code)
                records = fetch_stock_dividend(ts_code_full, delay=delay)

                # 只保留 imp_ann_date >= latest_imp_ann_date 的增量记录
                # 同时也保留 imp_ann_date 为空的记录（容错）
                new_records = [
                    r for r in records
                    if r.imp_ann_date is None or r.imp_ann_date >= latest_imp_ann_date
                ]

                if new_records:
                    written = upsert_events(session, new_records)
                    if written > 0:
                        batch_records += written
                        total_records += written
                        total_stocks += 1

                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"   进度 {batch_start + i + 1}/{len(stock_codes)} | 增 {total_records} 条 | 耗时 {elapsed:.1f}s")

            logger.info(f"  ✅ 本批增量完成: {batch_records} 条")

        elapsed = time.time() - start_time
        logger.info(f"\n🎉 增量拉取完成！")
        logger.info(f"  有增量事件股票: {total_stocks} 只")
        logger.info(f"  增量事件数: {total_records} 条")
        logger.info(f"  总耗时: {elapsed:.1f}s")
        return total_records

    finally:
        if close_session:
            session.close()


def main():
    parser = argparse.ArgumentParser(description="拉取分红送股数据")
    parser.add_argument("stock_code", nargs="?", default=None, help="股票代码（可选，不传则拉取全市场）")
    parser.add_argument("--batch", type=int, default=500, help="每批股票数（默认500）")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数")
    parser.add_argument("--incremental", action="store_true", help="增量拉取（按最新ann_date）")
    args = parser.parse_args()

    ensure_tables_exist()

    if args.incremental:
        fetch_dividend_incremental(batch_size=args.batch, delay=args.delay)
    elif args.stock_code:
        fetch_single_stock(args.stock_code, delay=args.delay)
    else:
        fetch_all_stocks(batch_size=args.batch, delay=args.delay)


if __name__ == "__main__":
    main()