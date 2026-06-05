"""
真实A股数据采集脚本 — 从Tushare Pro拉取数据写入MySQL

用法:
  python scripts/fetch_real_data.py                         # 拉取最近交易日数据
  python scripts/fetch_real_data.py 2026-06-05              # 拉取指定日期数据
  python scripts/fetch_real_data.py 2026-06-05 --top 100    # 仅拉取前100只（测试用）
  python scripts/fetch_real_data.py --history 30            # 拉取最近30个交易日的历史数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
import random
import concurrent.futures
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
from app.models.financial import Financial
from app.models.base import Base
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
# - 不含 turnover_rate

# 并发控制
INSERT_LOCK = Lock()
BATCH_RECORDS = []  # 全局批量插入缓冲区
BATCH_SIZE = 6000   # 每批插入条数
PROGRESS_LOCK = Lock()
TOTAL_DONE = 0
TOTAL_STOCKS = 0


def parse_args():
    parser = argparse.ArgumentParser(description="从Tushare Pro拉取真实A股数据到MySQL")
    parser.add_argument("date", nargs="?", help="交易日期 (YYYY-MM-DD)，默认最近交易日")
    parser.add_argument("--top", type=int, default=0, help="限制股票数量 (0=全部)")
    parser.add_argument("--history", type=int, default=0,
                        help="拉取最近N个交易日的历史数据（覆盖日期参数）")
    parser.add_argument("--skip-macro", action="store_true", help="跳过宏观数据")
    parser.add_argument("--skip-financial", action="store_true", help="跳过财务数据")
    parser.add_argument("--skip-stock-basic", action="store_true", help="跳过股票基础信息拉取")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="每次请求间隔秒数 (Tushare免费版限流，默认0.1s)")
    parser.add_argument("--workers", type=int, default=5,
                        help="并发线程数 (默认5，Tushare建议低并发)")
    return parser.parse_args()


def ensure_tables_exist():
    """确保数据表已创建"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")


def fetch_stock_basic(db: Session, max_retries: int = 3) -> int:
    """① 拉取全市场A股基础信息 → stock_basic（使用Tushare Pro）

    获取完整字段：ts_code, symbol, name, area, industry, fullname, enname,
    cnspell, market, exchange, curr_type, list_status, list_date,
    delist_date, is_hs, act_name, act_ent_type

    自动处理 Tushare 频率超限错误，等待 61秒 后重试。
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"正在获取全市场A股基础信息 (Tushare Pro)... 尝试 {attempt}/{max_retries}")

            df = pro.stock_basic(exchange='', list_status='L')
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


def _batch_insert_one(session, record: StockDaily):
    """将一条记录加入批量缓冲区，达到 BATCH_SIZE 自动提交"""
    global BATCH_RECORDS
    BATCH_RECORDS.append(record)
    if len(BATCH_RECORDS) >= BATCH_SIZE:
        _flush_batch(session)


def _flush_batch(session):
    """批量写入并清空缓冲区"""
    global BATCH_RECORDS
    if not BATCH_RECORDS:
        return
    batch = BATCH_RECORDS
    BATCH_RECORDS = []
    try:
        session.bulk_save_objects(batch)
        session.commit()
        logger.info(f"  📦 批量写入 {len(batch)} 条")
    except Exception as e:
        logger.warning(f"  ⚠️ 批量写入失败，逐条回退: {e}")
        session.rollback()
        for rec in batch:
            try:
                session.add(rec)
                session.commit()
            except Exception:
                session.rollback()


def _update_progress():
    """更新并打印进度"""
    global TOTAL_DONE
    with PROGRESS_LOCK:
        TOTAL_DONE += 1
        done = TOTAL_DONE
        total = TOTAL_STOCKS
    if total > 0 and done % 100 == 0:
        pct = done / total * 100
        logger.info(f"  📊 整体进度: {done}/{total} ({pct:.1f}%)")


def fetch_one_stock_history(ts_code: str, stock_code: str, stock_name: str,
                            start_date: str, end_date: str,
                            trade_dates: set, delay: float):
    """并发任务：拉取单只股票的历史日K线（使用Tushare Pro）"""
    local_records = []
    try:
        # Tushare pro.daily 接口
        df = pro.daily(
            ts_code=ts_code,
            start_date=start_date,  # YYYYMMDD
            end_date=end_date,      # YYYYMMDD
        )

        if df is None or df.empty:
            return []

        for _, row in df.iterrows():
            trade_date_str = str(row.get("trade_date", ""))
            if not trade_date_str:
                continue

            # Tushare 返回 trade_date 格式为 YYYYMMDD
            trade_date_obj = datetime.strptime(trade_date_str, "%Y%m%d").date()
            trade_date_fmt = trade_date_obj.strftime("%Y-%m-%d")

            # 只处理目标日期范围内的数据
            if trade_dates and trade_date_fmt not in trade_dates:
                continue

            # 单位换算：vol(手→股) *100, amount(千元→元) *1000
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
                volume=_safe_int(row.get("vol"), multiplier=100),    # 手 → 股
                amount=_safe_decimal(row.get("amount"), 2),          # 千元
            )

            # amount * 1000 从千元转元
            if record.amount is not None:
                record.amount = _safe_decimal(float(record.amount) * 1000, 2)

            local_records.append(record)

        _rate_limit(delay)
        _update_progress()
        return local_records

    except Exception as e:
        logger.warning(f"  ⚠️ [{stock_code}] {stock_name} 获取失败: {e}")
        return []


def _get_existing_keys(session, trade_dates: list) -> set:
    """查询数据库中已存在的 (stock_code, trade_date) 组合"""
    if not trade_dates:
        return set()
    date_tuple = tuple(trade_dates)
    sql = text("SELECT stock_code, trade_date FROM stock_daily WHERE trade_date IN :dates")
    result = session.execute(sql, {"dates": date_tuple}).fetchall()
    return {(str(r[0]), str(r[1])) for r in result}


def fetch_history_bulk(db: Session, codes_and_ts: list, start_date: str, end_date: str,
                       trade_dates: list, workers: int, delay: float, top_n: int = 0) -> int:
    """批量拉取多个股票的历史日K线"""
    if not codes_and_ts:
        return 0

    global TOTAL_STOCKS
    global TOTAL_DONE

    # 查已存在的记录，避免重复写入
    existing_keys = _get_existing_keys(db, trade_dates)
    logger.info(f"  数据库已有 {len(existing_keys)} 条(股票+日期)记录，将跳过已存在的")

    # 构建任务列表
    stock_list = []
    for ts_code, code, name in codes_and_ts:
        # 检查该股票在目标日期范围内是否已经有数据
        has_all = True
        for d in trade_dates:
            if (str(code), str(d)) not in existing_keys:
                has_all = False
                break
        if has_all:
            continue
        stock_list.append((ts_code, code, name))

    if top_n > 0:
        stock_list = stock_list[:top_n]

    TOTAL_STOCKS = len(stock_list)
    TOTAL_DONE = 0
    trade_dates_set = set(trade_dates)

    if not stock_list:
        logger.info("  ✅ 所有股票数据已存在，无需拉取")
        return 0

    logger.info(f"  需要拉取 {len(stock_list)} 只股票的历史数据，并发 {workers} 线程")

    # 单线程批量写入用
    insert_session = SessionLocal()
    total_inserted = 0

    try:
        # 使用线程池并发拉取
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for ts_code, code, name in stock_list:
                future = executor.submit(
                    fetch_one_stock_history,
                    ts_code, code, name,
                    start_date, end_date,
                    trade_dates_set,
                    delay,
                )
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                records = future.result()
                if records:
                    for rec in records:
                        _batch_insert_one(insert_session, rec)
                    total_inserted += len(records)

        # 写入剩余未刷新的批次
        _flush_batch(insert_session)
        logger.info(f"  ✅ 历史数据拉取完成，共写入 {total_inserted} 条记录")
        return total_inserted

    except Exception as e:
        logger.error(f"  ❌ 历史数据拉取异常: {e}")
        import traceback
        traceback.print_exc()
        return total_inserted
    finally:
        # 确保最后一批数据写入
        _flush_batch(insert_session)
        insert_session.close()


def _rate_limit(delay: float):
    """速率限制：睡眠 delay + 随机抖动（0~delay），模拟人类行为防封IP"""
    if delay <= 0:
        return
    jitter = random.uniform(0, delay)
    total = delay + jitter
    time.sleep(total)


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


def _pick_column(df, candidates: list) -> str | None:
    """从 DataFrame 列中按候选列表选取第一个存在的列名"""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def fetch_macro_data(db: Session, delay: float = 0.1) -> bool:
    """③ 拉取宏观经济数据 → macro_data（使用Tushare Pro）

    根据实际返回列名适配各接口。
    """
    try:
        logger.info("正在获取宏观经济数据 (Tushare Pro)...")

        today = date.today()

        # 检查今日是否已有数据
        existing = db.query(MacroData).filter(MacroData.data_date == today).first()
        if existing:
            logger.info("⏭️ 今日宏观数据已存在，跳过")
            return True

        macro = MacroData(data_date=today)

        # ── GDP（季度数据: cn_gdp）─ cols: quarter, gdp, gdp_yoy, pi, pi_yoy, si, si_yoy, ti, ti_yoy ──
        _rate_limit(delay)
        try:
            df = pro.cn_gdp()
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.gdp_yoy = _safe_series_get(last, "gdp_yoy")
                macro.gdp = _safe_series_get(last, "gdp")
                if macro.gdp_yoy is not None:
                    logger.info(f"  GDP同比: {macro.gdp_yoy}%")
                if macro.gdp is not None:
                    logger.info(f"  GDP: {macro.gdp}亿元")
        except Exception as e:
            logger.warning(f"  GDP获取失败: {e}")

        # ── CPI（月度: cn_cpi）─ cols: month, nt_val, nt_yoy, nt_mom, ... ──
        _rate_limit(delay)
        try:
            df = pro.cn_cpi()
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.cpi_yoy = _safe_series_get(last, "nt_yoy")
                macro.cpi_val = _safe_series_get(last, "nt_val")
                if macro.cpi_yoy is not None:
                    logger.info(f"  CPI同比: {macro.cpi_yoy}%")
        except Exception as e:
            logger.warning(f"  CPI获取失败: {e}")

        # ── PPI（月度: cn_ppi）─ cols: month, ppi_yoy, ... ──
        _rate_limit(delay)
        try:
            df = pro.cn_ppi()
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.ppi_yoy = _safe_series_get(last, "ppi_yoy")
                if macro.ppi_yoy is not None:
                    logger.info(f"  PPI同比: {macro.ppi_yoy}%")
        except Exception as e:
            logger.warning(f"  PPI获取失败: {e}")

        # ── PMI（月度: cn_pmi）─ 频率限制1次/小时 ──
        _rate_limit(delay)
        try:
            df = pro.cn_pmi(fields='month,pmi010000')
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.pmi = _safe_series_get(last, "pmi010000")
                if macro.pmi is not None:
                    logger.info(f"  制造业PMI: {macro.pmi}")
        except Exception as e:
            logger.warning(f"  PMI获取失败: {e}")

        # ── M2（货币供应量：cn_m，月度）──
        _rate_limit(delay)
        try:
            df = pro.cn_m(fields='month,m2,m2_yoy')
            if df is not None and not df.empty:
                # 过滤掉空值，取最新非空行
                valid = df.dropna(subset=['m2_yoy'])
                if not valid.empty:
                    last = valid.iloc[-1]
                    macro.m2_yoy = _safe_series_get(last, "m2_yoy")
                    if macro.m2_yoy is not None:
                        logger.info(f"  M2同比: {macro.m2_yoy}% (月份: {last.get('month')})")
        except Exception as e:
            logger.warning(f"  M2获取失败: {e}")

        # ── SHIBOR（日频: shibor）─ cols: date, on, 1w, 2w, 1m, 3m, 6m, 9m, 1y ──
        _rate_limit(delay)
        try:
            today_str = today.strftime("%Y%m%d")
            df = pro.shibor(start_date=today_str, end_date=today_str)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.shibor_on = _safe_series_get(last, "on")
                macro.shibor_1w = _safe_series_get(last, "1w")
                macro.shibor_1m = _safe_series_get(last, "1m")
                macro.shibor_1y = _safe_series_get(last, "1y")
                if macro.shibor_1m is not None:
                    logger.info(f"  SHIBOR隔夜: {macro.shibor_on}%, 1M: {macro.shibor_1m}%")
        except Exception as e:
            logger.warning(f"  Shibor获取失败: {e}")

        # ── 美元兑人民币汇率 ── 用户确认不需要，跳过
        _rate_limit(delay)
        pass

        # ── 沪深港通资金（日频: moneyflow_hsgt）─ cols: trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money, south_money ──
        _rate_limit(delay)
        try:
            today_str = today.strftime("%Y%m%d")
            df = pro.moneyflow_hsgt(start_date=today_str, end_date=today_str)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                # 所有值以字符串形式存储，需转换
                macro.hgt = _safe_series_get(last, "hgt")
                macro.sgt = _safe_series_get(last, "sgt")
                macro.north_flow = _safe_series_get(last, "north_money")
                if macro.hgt is not None:
                    logger.info(f"  沪股通: {macro.hgt:.2f}亿, 深股通: {macro.sgt:.2f}亿")
                if macro.north_flow is not None:
                    logger.info(f"  北向资金合计: {macro.north_flow:.2f}亿")
        except Exception as e:
            logger.warning(f"  沪深港通获取失败: {e}")

        # ── 美国国债收益率曲线（日频: us_tycr）─ 取3个代表性品种 ──
        _rate_limit(delay)
        try:
            today_str = today.strftime("%Y%m%d")
            df = pro.us_tycr(start_date=today_str, end_date=today_str)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                macro.us_y3m = _safe_series_get(last, "m3")    # 3个月（短期代表）
                macro.us_y2y = _safe_series_get(last, "y2")    # 2年期（中期代表）
                macro.us_y10y = _safe_series_get(last, "y10")  # 10年期（长期基准）
                if macro.us_y10y is not None:
                    logger.info(f"  美国国债 3m: {macro.us_y3m}%, 2y: {macro.us_y2y}%, 10y: {macro.us_y10y}%")
        except Exception as e:
            logger.warning(f"  美国国债收益率获取失败: {e}")

        # ── 社会融资规模（月度: sf_month）─ ──
        _rate_limit(delay)
        try:
            df = pro.sf_month(fields='month,stk_endval')
            if df is not None and not df.empty:
                # 过滤掉空值，取最新非空行
                valid = df.dropna(subset=['stk_endval'])
                if not valid.empty:
                    last = valid.iloc[-1]
                    val = _safe_series_get(last, "stk_endval")
                    if val is not None:
                        macro.margin_balance = round(val, 2)
                        logger.info(f"  社融存量期末值: {macro.margin_balance}万亿元 (月份: {last.get('month')})")
        except Exception as e:
            logger.warning(f"  社融存量获取失败: {e}")

        db.add(macro)
        db.commit()
        logger.info("✅ 宏观数据写入完成")
        return True
    except Exception as e:
        logger.error(f"❌ 获取宏观数据失败: {e}")
        db.rollback()
        return False


def main():
    args = parse_args()

    # 确保表存在
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
    elif args.date:
        dates = [args.date]
    else:
        latest = get_latest_trade_day()
        dates = [latest.strftime("%Y-%m-%d")]

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

        # 获取所有股票代码 (带 ts_code 映射)
        stocks = db.query(StockBasic.stock_code, StockBasic.stock_name).filter(
            StockBasic.is_active == 1
        ).all()
        # 构建 (ts_code, stock_code, stock_name) 元组列表
        codes_and_ts = [
            (get_ts_code(s.stock_code), s.stock_code, s.stock_name)
            for s in stocks
        ]
        logger.info(f"📋 待处理股票数: {len(codes_and_ts)}")

        if not codes_and_ts:
            logger.warning("⚠️ 没有可用的股票")
            return

        # ========== ② 批量拉取历史日K线 ==========
        logger.info(f"\n{'='*50}")
        logger.info("📊 开始批量拉取历史日K线数据 (Tushare Pro)")
        logger.info(f"{'='*50}")

        start_date = dates[0].replace("-", "")
        end_date = dates[-1].replace("-", "")

        total_records = fetch_history_bulk(
            db=db,
            codes_and_ts=codes_and_ts,
            start_date=start_date,
            end_date=end_date,
            trade_dates=dates,
            workers=args.workers,
            delay=args.delay,
            top_n=args.top,
        )

        # ========== ③ 宏观数据 ==========
        if not args.skip_macro:
            logger.info(f"\n{'='*50}")
            logger.info("📊 拉取宏观经济数据")
            logger.info(f"{'='*50}")
            fetch_macro_data(db, delay=args.delay)

        # ========== 统计 ==========
        logger.info(f"\n{'='*50}")
        logger.info("📊 采集完成统计")
        logger.info(f"{'='*50}")
        logger.info(f"  处理交易日: {len(dates)} 天 ({dates[0]} ~ {dates[-1]})")
        logger.info(f"  处理股票数: {len(codes_and_ts)} 只")
        logger.info(f"  写入行情数据: {total_records} 条")
        logger.info(f"  数据库股票总数: {db.query(StockBasic).count()}")
        logger.info(f"  日行情总记录数: {db.query(StockDaily).count()}")
        logger.info(f"  宏观数据条数: {db.query(MacroData).count()}")

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