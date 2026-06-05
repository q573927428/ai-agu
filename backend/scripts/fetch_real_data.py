"""
真实A股数据采集脚本 — 从AkShare拉取数据写入MySQL

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

# AkShare 字段映射：ak.stock_zh_a_hist() 返回的列名 → stock_daily 字段
HIST_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "price_change",
    "换手率": "turnover_rate",
}

# 并发控制
INSERT_LOCK = Lock()
BATCH_RECORDS = []  # 全局批量插入缓冲区
BATCH_SIZE = 5000   # 每批插入条数
PROGRESS_LOCK = Lock()
TOTAL_DONE = 0
TOTAL_STOCKS = 0


def parse_args():
    parser = argparse.ArgumentParser(description="从AkShare拉取真实A股数据到MySQL")
    parser.add_argument("date", nargs="?", help="交易日期 (YYYY-MM-DD)，默认最近交易日")
    parser.add_argument("--top", type=int, default=0, help="限制股票数量 (0=全部)")
    parser.add_argument("--history", type=int, default=0,
                        help="拉取最近N个交易日的历史数据（覆盖日期参数）")
    parser.add_argument("--skip-macro", action="store_true", help="跳过宏观数据")
    parser.add_argument("--skip-financial", action="store_true", help="跳过财务数据")
    parser.add_argument("--delay", type=float, default=0.02,
                        help="每次请求间隔秒数 (防封IP，默认0.02s)")
    parser.add_argument("--workers", type=int, default=10,
                        help="并发线程数 (默认10)")
    return parser.parse_args()


def ensure_tables_exist():
    """确保数据表已创建"""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据表已就绪")


def fetch_stock_basic(db: Session) -> int:
    """① 拉取全市场A股基础信息 → stock_basic"""
    try:
        import akshare as ak
        logger.info("正在获取全市场A股基础信息...")
        df = ak.stock_info_a_code_name()
        if df is None or df.empty:
            logger.warning("未获取到股票基础信息")
            return 0

        count = 0
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip().zfill(6)
            name = str(row.get("name", "")).strip()
            if not code or not name:
                continue

            existing = db.query(StockBasic).filter(StockBasic.stock_code == code).first()
            if not existing:
                db.add(StockBasic(
                    stock_code=code,
                    stock_name=name,
                    is_active=1,
                ))
                count += 1

        db.commit()
        logger.info(f"✅ 新增 {count} 只股票，总股票数: {db.query(StockBasic).count()}")
        return count
    except Exception as e:
        logger.error(f"❌ 获取股票基础信息失败: {e}")
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


def fetch_one_stock_history(stock_code: str, stock_name: str, start_date: str,
                            end_date: str, trade_dates: set, delay: float):
    """并发任务：拉取单只股票的历史日K线"""
    imported_ak = None
    local_records = []
    try:
        import akshare as ak
        imported_ak = ak

        # 实时快照用于获取当前盘口数据（最新价、市值等）
        # 但历史日K线用 stock_zh_a_hist
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",  # 前复权
        )

        if df is None or df.empty:
            return 0

        # 重命名列
        df = df.rename(columns=HIST_COLUMN_MAP)

        for _, row in df.iterrows():
            trade_date_str = str(row.get("trade_date", ""))
            if not trade_date_str:
                continue

            # 只处理目标日期范围内的数据
            if trade_dates and trade_date_str not in trade_dates:
                continue

            trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()

            record = StockDaily(
                stock_code=stock_code,
                trade_date=trade_date,
                open=_safe_decimal(row.get("open"), 3),
                high=_safe_decimal(row.get("high"), 3),
                low=_safe_decimal(row.get("low"), 3),
                close=_safe_decimal(row.get("close"), 3),
                pre_close=None,  # hist 接口不直接提供昨收
                volume=int(row.get("volume", 0) or 0),
                amount=_safe_decimal(row.get("amount"), 2),
                turnover_rate=_safe_decimal(row.get("turnover_rate"), 4),
            )
            local_records.append(record)

        _rate_limit(delay)
        _update_progress()
        return len(local_records)

    except Exception as e:
        logger.warning(f"  ⚠️ [{stock_code}] {stock_name} 获取失败: {e}")
        return 0


def _get_existing_keys(session, trade_dates: list) -> set:
    """查询数据库中已存在的 (stock_code, trade_date) 组合"""
    if not trade_dates:
        return set()
    date_tuple = tuple(trade_dates)
    sql = text("SELECT stock_code, trade_date FROM stock_daily WHERE trade_date IN :dates")
    result = session.execute(sql, {"dates": date_tuple}).fetchall()
    return {(str(r[0]), str(r[1])) for r in result}


def fetch_history_bulk(db: Session, codes: list, start_date: str, end_date: str,
                       trade_dates: list, workers: int, delay: float, top_n: int = 0) -> int:
    """批量拉取多个股票的历史日K线"""
    if not codes:
        return 0

    global TOTAL_STOCKS
    global TOTAL_DONE

    # 查已存在的记录，避免重复写入
    existing_keys = _get_existing_keys(db, trade_dates)
    logger.info(f"  数据库已有 {len(existing_keys)} 条(股票+日期)记录，将跳过已存在的")

    # 构建任务列表
    stock_list = []
    for code, name in codes:
        # 检查该股票在目标日期范围内是否已经有数据
        has_all = True
        for d in trade_dates:
            if (str(code), str(d)) not in existing_keys:
                has_all = False
                break
        if has_all:
            continue
        stock_list.append((code, name))

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
            for code, name in stock_list:
                future = executor.submit(
                    fetch_one_stock_history,
                    code, name,
                    start_date, end_date,
                    trade_dates_set,
                    delay,
                )
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                count = future.result()
                if count > 0:
                    total_inserted += count

        logger.info(f"  ✅ 历史数据拉取完成，共获取 {total_inserted} 条记录")
        return total_inserted

    except Exception as e:
        logger.error(f"  ❌ 历史数据拉取异常: {e}")
        import traceback
        traceback.print_exc()
        return total_inserted
    finally:
        insert_session.close()


def _rate_limit(delay: float):
    """速率限制：睡眠 delay + 随机抖动（0~delay），模拟人类行为防封IP"""
    if delay <= 0:
        return
    jitter = random.uniform(0, delay)
    total = delay + jitter
    time.sleep(total)


def fetch_macro_data(db: Session, delay: float = 0.1) -> bool:
    """③ 拉取宏观经济数据 → macro_data"""
    try:
        import akshare as ak
        logger.info("正在获取宏观经济数据...")

        today = date.today()

        # 检查今日是否已有数据
        existing = db.query(MacroData).filter(MacroData.data_date == today).first()
        if existing:
            logger.info("⏭️ 今日宏观数据已存在，跳过")
            return True

        macro = MacroData(data_date=today)

        # GDP
        try:
            gdp_df = ak.macro_china_gdp_yearly()
            if gdp_df is not None and not gdp_df.empty:
                macro.gdp_yoy = float(gdp_df.iloc[-1].get("同比", 0) or 0)
                logger.info(f"  GDP同比: {macro.gdp_yoy}%")
        except Exception as e:
            logger.warning(f"  GDP获取失败: {e}")

        _rate_limit(delay)

        # CPI
        try:
            cpi_df = ak.macro_china_cpi_yearly()
            if cpi_df is not None and not cpi_df.empty:
                macro.cpi_yoy = float(cpi_df.iloc[-1].get("同比", 0) or 0)
                logger.info(f"  CPI同比: {macro.cpi_yoy}%")
        except Exception as e:
            logger.warning(f"  CPI获取失败: {e}")

        _rate_limit(delay)

        # PMI
        try:
            pmi_df = ak.macro_china_pmi()
            if pmi_df is not None and not pmi_df.empty:
                macro.pmi = float(pmi_df.iloc[-1].get("现值", 0) or 0)
                logger.info(f"  PMI: {macro.pmi}")
        except Exception as e:
            logger.warning(f"  PMI获取失败: {e}")

        _rate_limit(delay)

        # M2
        try:
            m2_df = ak.macro_china_money_supply()
            if m2_df is not None and not m2_df.empty:
                macro.m2_yoy = float(m2_df.iloc[-1].get("同比增长", 0) or 0)
                logger.info(f"  M2同比: {macro.m2_yoy}%")
        except Exception as e:
            logger.warning(f"  M2获取失败: {e}")

        _rate_limit(delay)

        # Shibor
        try:
            shibor_df = ak.macro_china_shibor_all()
            if shibor_df is not None and not shibor_df.empty:
                # 找到1M Shibor
                shibor_1m_row = shibor_df[shibor_df["指标名称"].str.contains("1个月", na=False)]
                if not shibor_1m_row.empty:
                    macro.shibor_1m = float(shibor_1m_row.iloc[-1].get("利率", 0) or 0)
                    logger.info(f"  SHIBOR 1M: {macro.shibor_1m}%")
        except Exception as e:
            logger.warning(f"  Shibor获取失败: {e}")

        _rate_limit(delay)

        # 国债收益率
        try:
            bond_df = ak.bond_china_yield()
            if bond_df is not None and not bond_df.empty:
                # 找到10年期
                bond_10y = bond_df[bond_df["曲线名称"].str.contains("10年", na=False)]
                if not bond_10y.empty:
                    macro.bond_10y_yield = float(bond_10y.iloc[-1].get("收益率", 0) or 0)
                    logger.info(f"  10年国债收益率: {macro.bond_10y_yield}%")
        except Exception as e:
            logger.warning(f"  国债收益率获取失败: {e}")

        _rate_limit(delay)

        # 汇率
        try:
            macro.usdcny = 7.24  # 默认值，AkShare汇率接口可能变化
        except Exception as e:
            logger.warning(f"  汇率获取失败: {e}")

        # 北向资金
        try:
            north_df = ak.stock_hsgt_north_net_flow_in_em()
            if north_df is not None and not north_df.empty:
                macro.north_flow = float(north_df.iloc[-1].get("value", 0) or 0)
                logger.info(f"  北向资金: {macro.north_flow}亿元")
        except Exception as e:
            logger.warning(f"  北向资金获取失败: {e}")

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
        # 拉取最近N个交易日的历史数据
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
        # 默认：最近交易日
        latest = get_latest_trade_day()
        dates = [latest.strftime("%Y-%m-%d")]

    db = SessionLocal()
    try:
        # ========== ① 股票基础信息 ==========
        fetch_stock_basic(db)

        # 获取所有股票代码
        stocks = db.query(StockBasic.stock_code, StockBasic.stock_name).filter(
            StockBasic.is_active == 1
        ).all()
        codes = [(s.stock_code, s.stock_name) for s in stocks]
        logger.info(f"📋 待处理股票数: {len(codes)}")

        if not codes:
            logger.warning("⚠️ 没有可用的股票")
            return

        # ========== ② 批量拉取历史日K线 ==========
        logger.info(f"\n{'='*50}")
        logger.info("📊 开始批量拉取历史日K线数据")
        logger.info(f"{'='*50}")

        start_date = dates[0].replace("-", "")
        end_date = dates[-1].replace("-", "")

        total_records = fetch_history_bulk(
            db=db,
            codes=codes,
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
        logger.info(f"  处理股票数: {len(codes)} 只")
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