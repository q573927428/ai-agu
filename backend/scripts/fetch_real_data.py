"""
真实A股数据采集脚本 — 从Tushare Pro拉取数据写入MySQL

用法:
  python scripts/fetch_real_data.py                           # 拉取最近交易日数据
  python scripts/fetch_real_data.py 2026-06-05                # 拉取指定日期数据
  python scripts/fetch_real_data.py 2026-06-01 2026-06-05     # 拉取日期区间数据
  python scripts/fetch_real_data.py 2026-06-05 --top 100      # 仅拉取前100只（测试用）
  python scripts/fetch_real_data.py --history 30              # 拉取最近30个交易日的历史数据
  python scripts/fetch_real_data.py --full-financial          # 全量刷新财务数据（默认增量更新）
  python scripts/fetch_real_data.py --skip-financial          # 跳过财务数据拉取
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
import random
from threading import Lock
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from decimal import Decimal
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.utils.db_utils import SessionLocal, engine
from app.models.stock import StockBasic
from app.models.stock_daily import StockDaily
from app.models.macro import MacroData
from app.models.income import Income
from app.models.balancesheet import Balancesheet
from app.models.cashflow import Cashflow
from app.models.fina_indicator import FinaIndicator
from app.models.base import Base
from app.models.index_daily import IndexDaily
from app.utils.date_utils import is_trade_day, get_latest_trade_day

# ---------- Tushare Pro 初始化 ----------
import tushare as ts
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# ---------- 股票代码 → ts_code 映射规则 ----------
def get_ts_code(stock_code: str) -> str:
    """
    根据股票代码前3位判断交易所后缀
    000/001/002/003/300/301 → .SZ
    600/601/603/605/688/689 → .SH
    4xx/8xx → .BJ
    """
    prefix = stock_code[:3]
    if prefix in {"000", "001", "002", "003", "300", "301"}:
        return f"{stock_code}.SZ"
    elif prefix in {"600", "601", "603", "605", "688", "689"}:
        return f"{stock_code}.SH"
    else:
        return f"{stock_code}.BJ"


def extract_symbol(ts_code: str) -> str:
    """从 ts_code 中提取纯数字代码，如 000001.SZ → 000001"""
    return ts_code.split(".")[0]


# ---------- 字段映射 ----------
# Tushare daily() 返回字段 → stock_daily 字段名
# daily 返回: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
# - vol 单位: 手 (1手=100股)
# - amount 单位: 千元
# - pct_chg: 涨跌幅(%)

# ---------- 简易限速（按日期批量拉取，每秒1次即可）----------
LAST_REQUEST_TIME = 0
REQUEST_LOCK = Lock()


def _rate_limit(min_interval: float = 0.35) -> None:
    """简易速率限制，确保两次请求间隔不少于 min_interval 秒"""
    global LAST_REQUEST_TIME
    with REQUEST_LOCK:
        now = time.time()
        elapsed = now - LAST_REQUEST_TIME
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        LAST_REQUEST_TIME = time.time()


# ---------- 批量写入缓冲区 ----------
BATCH_RECORDS = []
BATCH_SIZE = 6000


def parse_args():
    parser = argparse.ArgumentParser(description="从Tushare Pro拉取真实A股数据到MySQL")
    parser.add_argument("dates", nargs="*", help="交易日期/区间 (YYYY-MM-DD)，可指定1个或2个日期")
    parser.add_argument("--top", type=int, default=0, help="限制股票数量 (0=全部)")
    parser.add_argument("--history", type=int, default=0,
                        help="拉取最近N个交易日的历史数据（覆盖日期参数）")
    parser.add_argument("--skip-macro", action="store_true", help="跳过宏观数据")
    parser.add_argument("--skip-financial", action="store_true", help="跳过财务数据")
    parser.add_argument("--full-financial", action="store_true", help="全量刷新财务数据（默认增量）")
    parser.add_argument("--skip-stock-basic", action="store_true", help="跳过股票基础信息拉取")
    parser.add_argument("--skip-index", action="store_true", help="跳过指数行情拉取")
    parser.add_argument("--delay", type=float, default=0.35,
                        help="每次请求间隔秒数 (默认0.35，Tushare免费版500次/分钟)")
    return parser.parse_args()


def ensure_tables_exist():
    """确保数据表已创建"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")


def fetch_stock_basic(db: Session, max_retries: int = 3) -> int:
    """① 拉取全市场A股基础信息 → stock_basic（使用Tushare Pro）"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"正在获取全市场A股基础信息 (Tushare Pro)... 尝试 {attempt}/{max_retries}")

            df = pro.stock_basic(
                exchange='', list_status='L',
                fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,'
                       'market,exchange,curr_type,list_status,list_date,delist_date,'
                       'is_hs,act_name,act_ent_type'
            )
            if df is None or df.empty:
                logger.warning("未获取到股票基础信息")
                return 0

            count = 0
            for _, row in df.iterrows():
                ts_code = str(row.get("ts_code", "")).strip()
                symbol = str(row.get("symbol", "")).strip()
                name = str(row.get("name", "")).strip()
                if not ts_code or not name:
                    continue

                code = symbol or extract_symbol(ts_code)
                list_date_val = None
                ld = str(row.get("list_date", "")).strip()
                if ld and ld != "None" and ld != "nan":
                    try:
                        list_date_val = datetime.strptime(ld, "%Y%m%d").date()
                    except ValueError:
                        pass

                delist_date_val = None
                dd = str(row.get("delist_date", "")).strip()
                if dd and dd != "None" and dd != "nan":
                    try:
                        delist_date_val = datetime.strptime(dd, "%Y%m%d").date()
                    except ValueError:
                        pass

                existing = db.query(StockBasic).filter(StockBasic.stock_code == code).first()
                if existing:
                    need_update = False
                    for fld in ["ts_code", "name", "area", "industry", "fullname", "enname",
                                "cnspell", "market", "exchange", "curr_type", "list_status",
                                "is_hs", "act_name", "act_ent_type"]:
                        val = row.get(fld)
                        if val is not None and str(val).strip() and str(val).strip() != "nan":
                            col_name = fld if fld != "name" else "stock_name"
                            if getattr(existing, col_name, None) != str(val).strip():
                                setattr(existing, col_name, str(val).strip())
                                need_update = True
                    if list_date_val and existing.list_date != list_date_val:
                        existing.list_date = list_date_val
                        need_update = True
                    if delist_date_val and existing.delist_date != delist_date_val:
                        existing.delist_date = delist_date_val
                        need_update = True
                    if need_update:
                        count += 1
                else:
                    kwargs = {
                        "stock_code": code,
                        "ts_code": ts_code,
                        "stock_name": str(row.get("name", "")).strip(),
                        "area": str(row.get("area", "")).strip() or None,
                        "industry": str(row.get("industry", "")).strip() or None,
                        "fullname": str(row.get("fullname", "")).strip() or None,
                        "enname": str(row.get("enname", "")).strip() or None,
                        "cnspell": str(row.get("cnspell", "")).strip() or None,
                        "market": str(row.get("market", "")).strip() or None,
                        "exchange": str(row.get("exchange", "")).strip() or None,
                        "curr_type": str(row.get("curr_type", "")).strip() or None,
                        "list_status": str(row.get("list_status", "")).strip() or "L",
                        "list_date": list_date_val,
                        "delist_date": delist_date_val,
                        "is_hs": str(row.get("is_hs", "")).strip() or None,
                        "act_name": str(row.get("act_name", "")).strip() or None,
                        "act_ent_type": str(row.get("act_ent_type", "")).strip() or None,
                        "is_active": 1,
                    }
                    db.add(StockBasic(**kwargs))
                    count += 1

            db.commit()
            logger.info(f"✅ 新增/更新 {count} 只股票，总股票数: {db.query(StockBasic).count()}")
            return count
        except Exception as e:
            err_msg = str(e)
            if "频率超限" in err_msg or "超限" in err_msg or "rate limit" in err_msg.lower():
                if attempt < max_retries:
                    wait_time = 61
                    logger.warning(f"⚠️ Tushare 频率超限，等待 {wait_time} 秒后重试 (第 {attempt} 次)...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ 已达最大重试次数 ({max_retries})，放弃获取股票基础信息")
            else:
                logger.error(f"❌ 获取股票基础信息失败: {e}")
                break

    db.rollback()
    return 0


def _safe_decimal(value, places=4):
    """安全转换为Decimal"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return round(Decimal(str(float(value))), places)
    except (ValueError, TypeError, Exception):
        return None


def _safe_int(value, multiplier=1):
    """安全转换为int，支持单位换算"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return int(float(value) * multiplier)
    except (ValueError, TypeError, Exception):
        return None


def _batch_insert_many(session, records: list):
    """将多条记录加入缓冲区，达到 BATCH_SIZE 自动提交"""
    global BATCH_RECORDS
    BATCH_RECORDS.extend(records)
    if len(BATCH_RECORDS) >= BATCH_SIZE:
        _flush_batch(session)


def _upsert_stock_daily(session, rec: StockDaily) -> bool:
    """使用 INSERT ... ON DUPLICATE KEY UPDATE 原子化写入"""
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
    return True


def _flush_batch(session):
    """批量写入并清空缓冲区 — 使用多行 INSERT ... ON DUPLICATE KEY UPDATE"""
    global BATCH_RECORDS
    if not BATCH_RECORDS:
        return
    batch = BATCH_RECORDS
    BATCH_RECORDS = []

    MAX_SQL_PARAMS = 500
    chunk_size = min(2000, MAX_SQL_PARAMS // 11)  # 每行11个参数
    total_written = 0

    for chunk_start in range(0, len(batch), chunk_size):
        chunk = batch[chunk_start:chunk_start + chunk_size]
        try:
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
                    open = VALUES(open), high = VALUES(high), low = VALUES(low),
                    close = VALUES(close), pre_close = VALUES(pre_close),
                    `change` = VALUES(`change`), pct_chg = VALUES(pct_chg),
                    volume = VALUES(volume), amount = VALUES(amount)
            """)
            session.execute(stmt, params)
            session.commit()
            total_written += len(chunk)
        except Exception as e:
            logger.warning(f"  ⚠️ 批量 upsert 失败({len(chunk)}条)，逐条回退: {e}")
            session.rollback()
            for rec in chunk:
                try:
                    _upsert_stock_daily(session, rec)
                    total_written += 1
                except Exception as ind_e:
                    session.rollback()
                    logger.warning(f"    ↪ 跳过记录: {rec.stock_code} {rec.trade_date} -> {ind_e}")
    logger.info(f"  📦 批量写入完成，共 {total_written}/{len(batch)} 条")


def _call_daily_by_date_with_retry(trade_date: str, max_retries: int = 3) -> pd.DataFrame:
    """
    调用 pro.daily(trade_date=...) — 1次请求拉取全市场，
    支持频率超限自动重试（等待61s）。

    这是速度优化的关键: 按日期拉取代替按股票拉取，
    全市场每天只需1次请求 vs 旧版5000+次请求。
    """
    for attempt in range(1, max_retries + 1):
        _rate_limit(0.35)
        try:
            df = pro.daily(trade_date=trade_date)
            return df
        except Exception as e:
            err_msg = str(e)
            if "频率超限" in err_msg or "超限" in err_msg or "rate limit" in err_msg.lower():
                if attempt < max_retries:
                    wait_time = 61
                    logger.warning(f"    ↪ [频率超限] {trade_date} 等待 {wait_time}s 重试 (第{attempt}次)")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"    ❌ [频率超限] {trade_date} 已达最大重试次数 ({max_retries})，放弃")
                    raise
            else:
                raise
    raise RuntimeError(f"调用 pro.daily(trade_date={trade_date}) 失败，已重试 {max_retries} 次")


def fetch_dates_batch(session: Session, trade_dates: list, delay: float = 0.35, top_n: int = 0) -> int:
    """
    按日期批量拉取全市场日行情（替代旧的按股票拉取方式）。

    每个交易日调用 1 次 pro.daily(trade_date=...) 即可获取全市场数据，
    相比按股票拉取（5000+次请求）效率提升 5000 倍。
    """
    if not trade_dates:
        return 0

    total_inserted = 0
    insert_session = SessionLocal()
    try:
        for i, trade_date in enumerate(trade_dates):
            trade_date_str = trade_date.replace("-", "")
            logger.info(f"  📅 [{i+1}/{len(trade_dates)}] 拉取 {trade_date} 全市场日行情...")

            df = _call_daily_by_date_with_retry(trade_date_str)

            if df is None or df.empty:
                logger.warning(f"    ⚠️ {trade_date} 无数据（非交易日/未入库）")
                continue

            if top_n > 0:
                df = df.head(top_n)

            records = []
            for _, row in df.iterrows():
                ts_code = str(row.get("ts_code", "")).strip()
                if not ts_code:
                    continue
                stock_code = ts_code.split(".")[0]

                record = StockDaily(
                    stock_code=stock_code,
                    trade_date=datetime.strptime(trade_date_str, "%Y%m%d").date(),
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
                if record.amount is not None:
                    record.amount = _safe_decimal(float(record.amount) * 1000, 2)

                records.append(record)

            if records:
                _batch_insert_many(insert_session, records)
                total_inserted += len(records)
                logger.info(f"    ✅ {trade_date} -> {len(records)} 条")

        _flush_batch(insert_session)
        logger.info(f"  ✅ 批量拉取完成，共写入 {total_inserted} 条记录")
        return total_inserted

    except Exception as e:
        logger.error(f"  ❌ 批量拉取异常: {e}")
        import traceback
        traceback.print_exc()
        return total_inserted
    finally:
        _flush_batch(insert_session)
        insert_session.close()


def _safe_float(value) -> float | None:
    """安全转换 float，NaN/None/空串 → None"""
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    try:
        v = float(value)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except (ValueError, TypeError, Exception):
        return None


def _safe_series_get(row, key: str) -> float | None:
    """从 Series 中安全取值并转为 float，NaN→None"""
    try:
        val = row.get(key)
        return _safe_float(val)
    except Exception:
        return None


def _get_recent_trade_days_str(n: int = 10) -> list[str]:
    """获取最近N个交易日，用于日频数据回退查询"""
    from app.utils.date_utils import get_latest_trade_day, is_trade_day
    from datetime import timedelta
    latest = get_latest_trade_day()
    days = [latest]
    current = latest - timedelta(days=1)
    while len(days) < n:
        if is_trade_day(current):
            days.append(current)
        current -= timedelta(days=1)
    return [d.strftime("%Y%m%d") for d in days]


def _fetch_last_valid_row(df: pd.DataFrame, field: str) -> pd.Series | None:
    """从 DataFrame 倒序遍历，返回第一个指定字段非空的行"""
    if df is None or df.empty:
        return None
    for i in range(len(df) - 1, -1, -1):
        row = df.iloc[i]
        if _safe_series_get(row, field) is not None:
            return row
    return None


def _fetch_daily_with_fallback(api_func, start_date: str, field: str,
                                recent_days: list[str], delay: float) -> pd.Series | None:
    """日频数据回退查询：从最近交易日开始往前尝试，直到有数据为止"""
    for day_str in recent_days:
        _rate_limit(delay)
        try:
            func_name = api_func.__name__
            if func_name == 'us_tycr':
                # us_tycr 用 date= 参数
                df = api_func(date=day_str)
            elif func_name in ('shibor', 'moneyflow_hsgt'):
                df = api_func(start_date=day_str, end_date=day_str)
            else:
                df = api_func(start_date=day_str, end_date=day_str)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                if _safe_series_get(last, field) is not None:
                    return last
        except Exception:
            continue
    return None


def fetch_macro_data(db: Session, delay: float = 0.1) -> bool:
    """③ 拉取宏观经济数据 → macro_data（使用Tushare Pro）

    ## 设计原则
    - data_date = 最近交易日（作为当日宏观快照的唯一标识）
    - UPSERT 模式：如果该日记录已存在，则 UPDATE 所有字段（填充之前缺失的 NULL）
    - 月/季度类数据（GDP/PMI/CPI等）倒序取第一条非空行
    - 日频数据（SHIBOR/北向资金/美债）回退查询最近10个交易日
    - 北向资金单位转换：Tushare 返回百万元 → 存储为亿元（/100）
    """
    try:
        logger.info("正在获取宏观经济数据 (Tushare Pro)...")

        # 最近10个交易日（用于日频数据回退查询）
        recent_days = _get_recent_trade_days_str(10)
        trade_day_str = recent_days[0]
        trade_day = datetime.strptime(trade_day_str, "%Y%m%d").date()

        # ========== UPSERT 策略 ==========
        existing = db.query(MacroData).filter(MacroData.data_date == trade_day).first()
        if existing:
            macro = existing
            is_new = False
            logger.info(f"📝 更新已有记录 {trade_day}（填充之前缺失的字段）")
        else:
            macro = MacroData(data_date=trade_day)
            is_new = True
            logger.info(f"🆕 创建新记录 {trade_day}")

        # ========== 1) GDP（季度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.cn_gdp()
            row = _fetch_last_valid_row(df, "gdp_yoy")
            if row is not None:
                macro.gdp_yoy = _safe_series_get(row, "gdp_yoy")
                macro.gdp = _safe_series_get(row, "gdp")
                logger.info(f"  GDP同比: {macro.gdp_yoy}%")
        except Exception as e:
            logger.warning(f"  GDP获取失败: {e}")

        # ========== 2) CPI（月度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.cn_cpi()
            row = _fetch_last_valid_row(df, "nt_yoy")
            if row is not None:
                macro.cpi_yoy = _safe_series_get(row, "nt_yoy")
                macro.cpi_val = _safe_series_get(row, "nt_val")
                logger.info(f"  CPI同比: {macro.cpi_yoy}%")
        except Exception as e:
            logger.warning(f"  CPI获取失败: {e}")

        # ========== 3) PPI（月度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.cn_ppi()
            row = _fetch_last_valid_row(df, "ppi_yoy")
            if row is not None:
                macro.ppi_yoy = _safe_series_get(row, "ppi_yoy")
                logger.info(f"  PPI同比: {macro.ppi_yoy}%")
        except Exception as e:
            logger.warning(f"  PPI获取失败: {e}")

        # ========== 4) PMI（月度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.cn_pmi(fields='month,pmi030000')
            row = _fetch_last_valid_row(df, "pmi030000")
            if row is not None:
                macro.pmi = _safe_series_get(row, "pmi030000")
                macro.pmi030000 = _safe_series_get(row, "pmi030000")
                logger.info(f"  制造业PMI(pmi030000): {macro.pmi}%")
        except Exception as e:
            logger.warning(f"  PMI获取失败: {e}")

        # ========== 5) M2（月度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.cn_m(fields='month,m2,m2_yoy')
            row = _fetch_last_valid_row(df, "m2_yoy")
            if row is not None:
                macro.m2_yoy = _safe_series_get(row, "m2_yoy")
                logger.info(f"  M2同比: {macro.m2_yoy}%")
        except Exception as e:
            logger.warning(f"  M2获取失败: {e}")

        # ========== 6) SHIBOR（日频，回退查询）==========
        row = _fetch_daily_with_fallback(pro.shibor, trade_day_str, "on", recent_days, delay)
        if row is not None:
            macro.shibor_on = _safe_series_get(row, "on")
            macro.shibor_1w = _safe_series_get(row, "1w")
            macro.shibor_1m = _safe_series_get(row, "1m")
            macro.shibor_1y = _safe_series_get(row, "1y")
            logger.info(f"  SHIBOR隔夜: {macro.shibor_on}%, 1M: {macro.shibor_1m}%")

        # ========== 7) 沪深港通（日频，回退查询；单位：百万元→亿元）==========
        row = _fetch_daily_with_fallback(pro.moneyflow_hsgt, trade_day_str, "hgt", recent_days, delay)
        if row is not None:
            hgt_raw = _safe_series_get(row, "hgt")
            sgt_raw = _safe_series_get(row, "sgt")
            north_raw = _safe_series_get(row, "north_money")
            if hgt_raw is not None:
                macro.hgt = round(hgt_raw / 100, 2)
                macro.sgt = round(sgt_raw / 100, 2) if sgt_raw is not None else None
                macro.north_flow = round(north_raw / 100, 2) if north_raw is not None else None
                logger.info(f"  沪股通: {macro.hgt:.2f}亿, 深股通: {macro.sgt:.2f}亿, 合计: {macro.north_flow:.2f}亿")

        # ========== 8) 美国国债收益率（日频，回退查询）==========
        row = _fetch_daily_with_fallback(pro.us_tycr, trade_day_str, "m3", recent_days, delay)
        if row is not None:
            macro.us_y3m = _safe_series_get(row, "m3")
            macro.us_y2y = _safe_series_get(row, "y2")
            macro.us_y10y = _safe_series_get(row, "y10")
            logger.info(f"  美国国债 3m: {macro.us_y3m}%, 2y: {macro.us_y2y}%, 10y: {macro.us_y10y}%")

        # ========== 9) 社融（月度数据，取最新有效行）==========
        _rate_limit(delay)
        try:
            df = pro.sf_month(fields='month,stk_endval')
            row = _fetch_last_valid_row(df, "stk_endval")
            if row is not None:
                val = _safe_series_get(row, "stk_endval")
                if val is not None:
                    macro.margin_balance = round(val, 2)
                    logger.info(f"  社融存量期末值: {macro.margin_balance}万亿元")
        except Exception as e:
            logger.warning(f"  社融存量获取失败: {e}")

        # ========== 写入数据库 ==========
        if is_new:
            db.add(macro)
        db.commit()
        logger.info(f"✅ 宏观数据写入完成 (data_date={trade_day})")
        return True
    except Exception as e:
        logger.error(f"❌ 获取宏观数据失败: {e}")
        db.rollback()
        return False


def _financial_upsert(session: Session, table_model, records: list, unique_cols: list):
    """批量 upsert 财务数据（逐条 INSERT ... ON DUPLICATE KEY UPDATE）"""
    if not records:
        return
    table_name = table_model.__tablename__
    for rec in records:
        try:
            cols = list(rec.keys())
            # 构建唯一键条件
            where_clause = " AND ".join([f"`{c}` = :{c}_uk" for c in unique_cols])
            uk_params = {f"{c}_uk": rec[c] for c in unique_cols}
            # 先查是否存在
            stmt_check = text(f"SELECT id FROM `{table_name}` WHERE {where_clause} LIMIT 1")
            result = session.execute(stmt_check, uk_params).fetchone()
            if result:
                # UPDATE
                set_clause = ", ".join([f"`{c}` = :{c}" for c in cols])
                stmt = text(f"UPDATE `{table_name}` SET {set_clause} WHERE id = :row_id")
                rec["row_id"] = result[0]
                session.execute(stmt, rec)
            else:
                # INSERT
                col_names = ", ".join([f"`{c}`" for c in cols])
                val_placeholders = ", ".join([f":{c}" for c in cols])
                stmt = text(f"INSERT INTO `{table_name}` ({col_names}) VALUES ({val_placeholders})")
                session.execute(stmt, rec)
        except Exception as e:
            session.rollback()
            logger.warning(f"  ⚠️ 财务 upsert 跳过: {e}")
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"  ⚠️ 财务批量提交失败，逐条回退: {e}")
        for rec in records:
            try:
                cols = list(rec.keys())
                col_names = ", ".join([f"`{c}`" for c in cols])
                val_placeholders = ", ".join([f":{c}" for c in cols])
                stmt = text(f"INSERT INTO `{table_name}` ({col_names}) VALUES ({val_placeholders}) "
                            f"ON DUPLICATE KEY UPDATE " +
                            ", ".join([f"`{c}` = VALUES(`{c}`)" for c in cols if c not in unique_cols + ["id"]]))
                session.execute(stmt, rec)
                session.commit()
            except Exception as ind_e:
                session.rollback()
                logger.warning(f"    ↪ 跳过财务记录: {ind_e}")


def _safe_date_str(val) -> str | None:
    """安全转换日期字符串 YYYYMMDD → YYYY-MM-DD"""
    if val is None or (isinstance(val, float) and np.isnan(val)):
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


def _get_next_report_periods(latest_end_date: date) -> list[str]:
    """
    根据数据库中已有的最新 end_date，计算需要拉取的下一个报告期。

    中国A股财报周期：
      - 一季报: 03-31 (Q1)
      - 半年报: 06-30 (H1 / Q2)
      - 三季报: 09-30 (Q3)
      - 年报:   12-31 (Annual / Q4)

    截止日期（必须在此前发布）：
      - 一季报: 4月30日
      - 半年报: 8月31日
      - 三季报: 10月31日
      - 年报:   次年4月30日

    判断逻辑：
      如果最新数据到 2026-03-31，则检查 2026-06-30 是否已过截止日期，
      已过则拉取，否则说明半年报还没出，没有新数据。
    """
    today = date.today()
    year = latest_end_date.year
    month = latest_end_date.month

    # 确定当前数据覆盖到哪个季度
    if month <= 3:
        current_season = 1  # 最新到 Q1
    elif month <= 6:
        current_season = 2  # 最新到 H1
    elif month <= 9:
        current_season = 3  # 最新到 Q3
    else:
        current_season = 4  # 最新到年报

    # 计算下一个季度的截止日期
    next_periods = []
    while len(next_periods) < 4:  # 最多看未来4个季度
        if current_season == 1:
            # 一季报 → 下一报告期是半年报 06-30，截止 08-31
            period_date = date(year, 6, 30)
            deadline = date(year, 8, 31)
        elif current_season == 2:
            # 半年报 → 三季报 09-30，截止 10-31
            period_date = date(year, 9, 30)
            deadline = date(year, 10, 31)
        elif current_season == 3:
            # 三季报 → 年报 12-31，截止次年 04-30
            period_date = date(year, 12, 31)
            deadline = date(year + 1, 4, 30)
        else:
            # 年报 → 次年一季报 03-31，截止 04-30
            period_date = date(year + 1, 3, 31)
            deadline = date(year + 1, 4, 30)

            # 如果截止日期已过，且该报告期有价值（需要拉取）
        if today > deadline and period_date > latest_end_date:
            next_periods.append(period_date.strftime("%Y%m%d"))
            # 继续检查下一个季度
            current_season += 1
            if current_season > 4:
                current_season = 1
                year += 1
            continue
        else:
            break

    return next_periods


def fetch_financial_data(db: Session, delay: float = 0.35, top_n: int = 0, full_refresh: bool = False) -> bool:
    """
    ④ 拉取上市公司财务数据（Tushare Pro）- 支持增量更新
    - pro.income()        → income 表 (利润表)
    - pro.balancesheet()  → balancesheet 表 (资产负债表)
    - pro.cashflow()      → cashflow 表 (现金流量表)
    - pro.fina_indicator() → fina_indicator 表 (财务指标)

    增量更新策略（正确使用 Tushare period 参数）：
      1. 检测每张表的最大 end_date
      2. 计算下一个需要拉取的报告期（如 Q2 半年报 20260630）
      3. 如果该报告期已过截止日期（已发布），仅拉取该 period 的数据
      4. 如果无新报告期，直接跳过整张表的拉取（零请求）

    注意（来自 Tushare 官方文档）：
      income/balancesheet/cashflow 的 start_date/end_date 参数过滤的是
      "公告日期(ann_date)"，不是报告期。要过滤报告期必须使用 period 参数。
    """
    from sqlalchemy import func

    # 获取所有股票列表
    stocks = db.query(StockBasic.stock_code, StockBasic.ts_code).all()
    if top_n > 0:
        stocks = stocks[:top_n]
    total = len(stocks)
    logger.info(f"📊 将拉取 {total} 只股票的财务数据...")

    api_configs = [
        ("利润表", pro.income, Income, "income", ["stock_code", "end_date", "report_type"]),
        ("资产负债表", pro.balancesheet, Balancesheet, "balancesheet", ["stock_code", "end_date", "report_type"]),
        ("现金流量表", pro.cashflow, Cashflow, "cashflow", ["stock_code", "end_date", "report_type"]),
        ("财务指标", pro.fina_indicator, FinaIndicator, "fina_indicator", ["stock_code", "end_date"]),
    ]

    for api_name, api_func, model_cls, table_name, unique_keys in api_configs:
        logger.info(f"  ── 拉取 {api_name} ({table_name}) ──")

        # === 计算需要拉取的报告期 ===
        if not full_refresh:
            latest_record = db.query(func.max(model_cls.end_date)).scalar()
            if latest_record is not None:
                next_periods = _get_next_report_periods(latest_record)
                if not next_periods:
                    logger.info(f"    ✅ 无新财报期（库内最新 {latest_record}，截至今日尚未有新的财报发布），跳过 {api_name}")
                    continue
                logger.info(f"    📅 增量模式：库内最新 {latest_record} → 需拉取报告期: {next_periods}")
            else:
                next_periods = []  # 空表=全量拉取
                logger.info(f"    📅 全量模式（首次）：{table_name} 表为空，拉取全部历史数据")
        else:
            next_periods = []
            logger.info(f"    📅 全量刷新模式（--full-financial）：重新拉取 {table_name} 全部历史数据")

        all_records = []
        success_count = 0
        skip_count = 0
        error_count = 0

        for idx, (stock_code, ts_code) in enumerate(stocks):
            if idx % 100 == 0 and idx > 0:
                logger.info(f"    [{idx}/{total}] {api_name} 处理中... ({success_count} 成功, {skip_count} 跳过)")

            _rate_limit(delay)
            try:
                # 正确使用 period 参数过滤报告期（非 start_date 公告日期）
                kwargs = {"ts_code": ts_code}
                if next_periods:
                    # 增量模式：只拉取特定报告期
                    kwargs["period"] = next_periods[0]
                df = api_func(**kwargs)
            except Exception as e:
                err_msg = str(e)
                if "频率超限" in err_msg or "超限" in err_msg or "rate limit" in err_msg.lower():
                    logger.warning(f"    ⚠️ [频率超限] 等待61s...")
                    time.sleep(61)
                    try:
                        kwargs = {"ts_code": ts_code}
                        if next_periods:
                            kwargs["period"] = next_periods[0]
                        df = api_func(**kwargs)
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
                    # fina_indicator 表没有 report_type
                    rec = {
                        "stock_code": stock_code,
                        "end_date": end_date_val,
                    }
                else:
                    report_type = int(row.get("report_type", 1)) if not (isinstance(row.get("report_type"), float) and np.isnan(row.get("report_type"))) else 1
                    rec = {
                        "stock_code": stock_code,
                        "end_date": end_date_val,
                        "report_type": report_type,
                    }

                # 通用字段映射（基于 Tushare Pro 实际返回列名）
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
                        if val is not None and not (isinstance(val, float) and np.isnan(val)):
                            rec[dst_col] = float(val)

                # 避免 profit=0 被 Tushare 返回 NaN 导致无数据
                all_records.append(rec)
                success_count += 1

            # 每500条批量写入一次
            if len(all_records) >= 500:
                _financial_upsert(db, model_cls, all_records, unique_keys)
                all_records = []

        # 最后一批写入
        if all_records:
            _financial_upsert(db, model_cls, all_records, unique_keys)

        total_in_db = db.query(model_cls).count()
        logger.info(f"    ✅ {api_name} 完成: {success_count} 条, 跳过 {skip_count}, 错误 {error_count}, 库内总计 {total_in_db}")

    logger.info("✅ 所有财务数据拉取完成")
    return True


def main():
    args = parse_args()

    ensure_tables_exist()

    # 确定要拉取的日期列表
    if args.history > 0:
        today = datetime.now()
        dates = []
        current = today
        while len(dates) < args.history:
            if is_trade_day(current):
                dates.append(current.strftime("%Y-%m-%d"))
            current -= timedelta(days=1)
        dates.reverse()
        logger.info(f"将拉取最近 {len(dates)} 个交易日的历史数据: {dates[0]} ~ {dates[-1]}")
    elif len(args.dates) == 2:
        start = datetime.strptime(args.dates[0], "%Y-%m-%d")
        end = datetime.strptime(args.dates[1], "%Y-%m-%d")
        dates = []
        current = start
        while current <= end:
            if is_trade_day(current):
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        logger.info(f"日期区间 {args.dates[0]} ~ {args.dates[1]}: {len(dates)} 个交易日")
    elif len(args.dates) == 1:
        dates = [args.dates[0]]
        logger.info(f"指定日期: {dates[0]}")
    else:
        latest = get_latest_trade_day()
        dates = [latest.strftime("%Y-%m-%d")]
        logger.info(f"默认最近交易日: {dates[0]}")

    db = SessionLocal()
    try:
        # ========== ① 股票基础信息 ==========
        stock_count = db.query(StockBasic).count()
        if args.skip_stock_basic:
            logger.info("⏭️ 已指定 --skip-stock-basic，跳过股票基础信息拉取")
        elif stock_count > 1000:
            logger.info(f"⏭️ 数据库已有 {stock_count} 只股票，跳过 stock_basic 拉取（如需刷新请使用 --skip-stock-basic 禁用此检查）")
        else:
            fetch_stock_basic(db)

        # ========== ② 按日期批量拉取日K线（不再按股票拉取）==========
        logger.info(f"\n{'='*50}")
        logger.info("📊 按日期批量拉取日K线 (pro.daily(trade_date=...))")
        logger.info("    每天1次请求拉全市场 → 替代旧版按股票拉取(5000+次)")
        logger.info(f"{'='*50}")

        total_records = fetch_dates_batch(
            session=db,
            trade_dates=dates,
            delay=args.delay,
            top_n=args.top,
        )

        # ========== ③ 指数行情 ==========
        if not args.skip_index:
            logger.info(f"\n{'='*50}")
            logger.info("📊 拉取指数行情 (pro.index_daily)")
            logger.info(f"{'='*50}")
            # 需要跟踪的核心指数
            index_ts_codes = [
                "000001.SH",  # 上证指数
                "399001.SZ",  # 深证成指
                "000300.SH",  # 沪深300
                "000016.SH",  # 上证50
                "000905.SH",  # 中证500
                "399006.SZ",  # 创业板指
                "000688.SH",  # 科创50
            ]
            total_index_count = 0
            for dt in dates:
                trade_date_str = dt.replace("-", "")
                logger.info(f"  拉取指数 {dt}...")
                for ts_code in index_ts_codes:
                    _rate_limit(args.delay)
                    try:
                        df = pro.index_daily(ts_code=ts_code, trade_date=trade_date_str)
                        if df is not None and not df.empty:
                            row = df.iloc[0]
                            existing = (
                                db.query(IndexDaily)
                                .filter(
                                    IndexDaily.ts_code == ts_code,
                                    IndexDaily.trade_date == dt,
                                )
                                .first()
                            )
                            if existing:
                                continue
                            rec = IndexDaily(
                                ts_code=ts_code,
                                trade_date=datetime.strptime(trade_date_str, "%Y%m%d").date(),
                                open=_safe_decimal(row.get("open"), 3),
                                high=_safe_decimal(row.get("high"), 3),
                                low=_safe_decimal(row.get("low"), 3),
                                close=_safe_decimal(row.get("close"), 3),
                                pre_close=_safe_decimal(row.get("pre_close"), 3),
                                change=_safe_decimal(row.get("change"), 3),
                                pct_chg=_safe_decimal(row.get("pct_chg"), 6),
                                vol=_safe_decimal(row.get("vol"), 2),
                                amount=_safe_decimal(row.get("amount"), 2),
                            )
                            db.add(rec)
                            total_index_count += 1
                        # else: 指数当天无交易数据（非交易日），跳过
                    except Exception as e:
                        err_msg = str(e)
                        if "频率超限" in err_msg or "超限" in err_msg or "rate limit" in err_msg.lower():
                            logger.warning(f"    ⚠️ [{ts_code}] 频率超限，等待61s...")
                            time.sleep(61)
                        else:
                            logger.warning(f"    ⚠️ [{ts_code}] {dt} 获取失败: {e}")
                db.commit()
                logger.info(f"    ✅ {dt} -> {len(index_ts_codes)} 个指数")
            logger.info(f"  ✅ 指数行情拉取完成，库内总计: {db.query(IndexDaily).count()}")

        # ========== ④ 宏观数据 ==========
        if not args.skip_macro:
            logger.info(f"\n{'='*50}")
            logger.info("📊 拉取宏观经济数据")
            logger.info(f"{'='*50}")
            fetch_macro_data(db, delay=args.delay)

        # ========== ④ 财务数据 ==========
        if not args.skip_financial:
            logger.info(f"\n{'='*50}")
            logger.info("📊 拉取上市公司财务数据")
            logger.info("  利润表 → income | 资产负债表 → balancesheet")
            logger.info("  现金流量表 → cashflow | 财务指标 → fina_indicator")
            logger.info(f"{'='*50}")
            fetch_financial_data(db, delay=args.delay, top_n=args.top, full_refresh=args.full_financial)

        # ========== 统计 ==========
        logger.info(f"\n{'='*50}")
        logger.info("📊 采集完成统计")
        logger.info(f"{'='*50}")
        logger.info(f"  处理交易日: {len(dates)} 天 ({dates[0]} ~ {dates[-1]})")
        logger.info(f"  写入行情数据: {total_records} 条")
        logger.info(f"  数据库股票总数: {db.query(StockBasic).count()}")
        logger.info(f"  日行情总记录数: {db.query(StockDaily).count()}")
        logger.info(f"  宏观数据条数: {db.query(MacroData).count()}")
        logger.info(f"  指数行情条数: {db.query(IndexDaily).count()}")
        logger.info(f"  利润表记录数: {db.query(Income).count()}")
        logger.info(f"  资产负债表记录数: {db.query(Balancesheet).count()}")
        logger.info(f"  现金流量表记录数: {db.query(Cashflow).count()}")
        logger.info(f"  财务指标记录数: {db.query(FinaIndicator).count()}")

    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
    except Exception as e:
        logger.error(f"❌ 采集过程异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

    logger.info("\n💡 下一步: python scripts/run_pipeline.py [日期]")


if __name__ == "__main__":
    main()