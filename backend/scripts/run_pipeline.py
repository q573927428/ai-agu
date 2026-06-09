"""
一键运行完整流水线（整合 fetch_real_data 与 pipeline）

用法（等价于原来的 fetch_real_data.py）:
  python scripts/run_pipeline.py                           # 拉取最近交易日数据 + 完整流水线
  python scripts/run_pipeline.py 2026-06-05                # 指定日期 + 完整流水线
  python scripts/run_pipeline.py 2026-06-01 2026-06-05     # 日期区间 + 完整流水线
  python scripts/run_pipeline.py --history 30               # 最近30个交易日 + 完整流水线
  python scripts/run_pipeline.py --fetch-only              # 仅拉取数据，不跑后续流水线
  python scripts/run_pipeline.py --skip-financial          # 拉取数据时跳过财务数据
  python scripts/run_pipeline.py --top 100                 # 仅处理前100只（测试用）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
from datetime import datetime, date, timedelta
from loguru import logger
import pandas as pd
from sqlalchemy.orm import Session
from app.utils.db_utils import SessionLocal
from app.services.factor_engine import FactorEngine
from app.services.label_generator import LabelGenerator
from app.services.predictor import Predictor
from app.services.ranking_service import RankingService
from app.services.trainer import Trainer

# ---------- 导入 fetch_real_data 中的函数 ----------
from scripts.fetch_real_data import (
    ensure_tables_exist,
    fetch_stock_basic,
    fetch_dates_batch,
    fetch_macro_data,
    fetch_financial_data,
)


def _check_and_train_model(db: Session, trade_date: str) -> bool:
    """检查是否有活跃模型，如果没有则尝试训练

    Returns:
        bool: 模型是否就绪
    """
    from app.models.model_record import ModelRecord
    from app.models.stock_daily import StockDaily

    has_model = db.query(ModelRecord).filter(ModelRecord.is_active == 1).first()
    if has_model:
        return True

    logger.warning("⚠️ 没有活跃模型，尝试训练...")

    # 获取已有历史交易日，用于批量计算因子
    trade_dates = [
        r[0] for r in db.query(StockDaily.trade_date)
        .distinct()
        .order_by(StockDaily.trade_date.asc())
        .all()
    ]

    if len(trade_dates) < 25:
        logger.warning(f"历史交易日不足(只有{len(trade_dates)}天)，无法训练")
        return False

    # 取前80%作为训练用日期
    train_dates = [str(d) for d in trade_dates[:int(len(trade_dates) * 0.8)]]
    if len(train_dates) < 10:
        logger.warning("有效训练日期不足")
        return False

    logger.info(f"批量计算 {len(train_dates)} 个交易日的历史因子...")

    engine = FactorEngine(db)
    factor_count = 0
    # 倒序遍历，保留最新的因子数据
    for dt in reversed(train_dates):
        df = engine.compute_all(dt)
        if not df.empty:
            engine.save_factors(df)
            factor_count += len(df)

    logger.info(f"历史因子计算完成: {factor_count} 条")

    # 检查因子表是否有数据
    from app.models.factor import FactorStore
    total_factors = db.query(FactorStore).count()
    if total_factors == 0:
        logger.warning("因子表中无数据，无法训练")
        return False

    logger.info(f"因子表总计: {total_factors} 条")

    # 训练模型
    train_start = train_dates[0]
    train_end = train_dates[-1]
    trainer = Trainer(db)
    result = trainer.train(start_date=train_start, end_date=train_end)

    if result.get("status") == "success":
        if result.get("note") == "multi-model ensemble":
            logger.info(
                f"✅ 多模型集成训练成功: "
                f"{result['ensemble_size']} 个子模型, "
                f"IC均值={result['valid_ic_mean']:.4f}"
            )
        else:
            logger.info(f"✅ 模型训练成功: {result['model_version']}, IC={result['valid_ic']:.4f}")
        return True
    else:
        logger.warning(f"⚠️ 模型训练失败: {result.get('message', '未知错误')}")
        return False


def parse_args():
    """统一参数解析 — 合并 fetch_real_data 与 run_pipeline 的参数"""
    parser = argparse.ArgumentParser(
        description="数据采集 + 完整流水线（整合 fetch_real_data 与 run_pipeline）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/run_pipeline.py                                    # 拉取最近交易日数据 + 流水线
  python scripts/run_pipeline.py 2026-06-05                         # 指定日期 + 流水线
  python scripts/run_pipeline.py 2026-06-01 2026-06-05              # 日期区间 + 流水线
  python scripts/run_pipeline.py 2026-06-05 --top 100               # 仅前100只（测试用）
  python scripts/run_pipeline.py --history 30                       # 最近30个交易日 + 流水线
  python scripts/run_pipeline.py --fetch-only                       # 仅拉取数据，不跑流水线
  python scripts/run_pipeline.py --full-financial                   # 全量刷新财务数据
  python scripts/run_pipeline.py --skip-financial                   # 跳过财务数据
  python scripts/run_pipeline.py --skip-macro                       # 跳过宏观数据
  python scripts/run_pipeline.py --skip-stock-basic                 # 跳过股票基础信息
  python scripts/run_pipeline.py --skip-index                       # 跳过指数行情
        """,
    )
    # ---------- 日期参数 ----------
    parser.add_argument("dates", nargs="*", help="交易日期/区间 (YYYY-MM-DD)，可指定1个或2个日期")
    parser.add_argument("--history", type=int, default=0,
                        help="拉取最近N个交易日的历史数据（覆盖日期参数）")
    parser.add_argument("--top", type=int, default=0,
                        help="限制股票数量 (0=全部)")

    # ---------- 跳过/选项参数 ----------
    parser.add_argument("--fetch-only", action="store_true",
                        help="仅拉取数据，不跑后续流水线（因子计算/预测/排名）")
    parser.add_argument("--skip-macro", action="store_true", help="跳过宏观数据")
    parser.add_argument("--skip-financial", action="store_true", help="跳过财务数据")
    parser.add_argument("--full-financial", action="store_true",
                        help="全量刷新财务数据（默认增量）")
    parser.add_argument("--skip-stock-basic", action="store_true",
                        help="跳过股票基础信息拉取")
    parser.add_argument("--skip-index", action="store_true", help="跳过指数行情拉取")

    # ---------- 性能参数 ----------
    parser.add_argument("--delay", type=float, default=0.35,
                        help="每次请求间隔秒数 (默认0.35，Tushare免费版500次/分钟)")
    return parser.parse_args()


def run_fetch(args, db: Session) -> list:
    """
    拉取数据（等价于 fetch_real_data.py 的 main 逻辑）

    Returns:
        list: 拉取的交易日列表
    """
    ensure_tables_exist()

    # 确定要拉取的日期列表
    if args.history > 0:
        today = datetime.now()
        dates = []
        current = today
        while len(dates) < args.history:
            from app.utils.date_utils import is_trade_day
            if is_trade_day(current):
                dates.append(current.strftime("%Y-%m-%d"))
            current -= timedelta(days=1)
        dates.reverse()
        logger.info(f"将拉取最近 {len(dates)} 个交易日的历史数据: {dates[0]} ~ {dates[-1]}")
    elif len(args.dates) == 2:
        from app.utils.date_utils import is_trade_day
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
        from app.utils.date_utils import get_latest_trade_day
        latest = get_latest_trade_day()
        dates = [latest.strftime("%Y-%m-%d")]
        logger.info(f"默认最近交易日: {dates[0]}")

    # ========== ① 股票基础信息 ==========
    from app.models.stock import StockBasic
    stock_count = db.query(StockBasic).count()
    if args.skip_stock_basic:
        logger.info("⏭️ 已指定 --skip-stock-basic，跳过股票基础信息拉取")
    elif stock_count > 1000:
        logger.info(f"⏭️ 数据库已有 {stock_count} 只股票，跳过 stock_basic 拉取（如需刷新请使用 --skip-stock-basic 禁用此检查）")
    else:
        fetch_stock_basic(db)

    # ========== ② 按日期批量拉取日K线 ==========
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
        import tushare as ts
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
        TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
        if TUSHARE_TOKEN:
            ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()

        from scripts.fetch_real_data import _safe_decimal, _rate_limit
        from app.models.index_daily import IndexDaily

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

    # ========== ⑤ 财务数据 ==========
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
    from app.models.stock_daily import StockDaily
    logger.info(f"  日行情总记录数: {db.query(StockDaily).count()}")
    from app.models.macro import MacroData
    logger.info(f"  宏观数据条数: {db.query(MacroData).count()}")
    from app.models.index_daily import IndexDaily
    logger.info(f"  指数行情条数: {db.query(IndexDaily).count()}")
    from app.models.income import Income
    logger.info(f"  利润表记录数: {db.query(Income).count()}")
    from app.models.balancesheet import Balancesheet
    logger.info(f"  资产负债表记录数: {db.query(Balancesheet).count()}")
    from app.models.cashflow import Cashflow
    logger.info(f"  现金流量表记录数: {db.query(Cashflow).count()}")
    from app.models.fina_indicator import FinaIndicator
    logger.info(f"  财务指标记录数: {db.query(FinaIndicator).count()}")

    return dates


def run_pipeline(trade_date: str, top_n: int = 0, args=None):
    """运行完整流水线（因子计算 → 标签 → 预测 → 排名）

    Args:
        trade_date: 目标交易日期
        top_n: 限制处理的股票数量，0=全部
        args: 完整的命令行参数对象（可选，提供更多配置）
    """
    logger.info(f"\n{'='*50}")
    logger.info(f"🚀 开始运行流水线: {trade_date}")
    logger.info(f"{'='*50}")
    if top_n > 0:
        logger.info(f"⚠️ 限制模式: 仅处理前 {top_n} 只股票")

    db = SessionLocal()
    try:
        # Step 1: 增量拉取分红送股数据
        logger.info("[1/8] 增量拉取分红送股数据...")
        from scripts.fetch_dividend import fetch_dividend_incremental
        dividend_count = fetch_dividend_incremental(session=db, delay=0.3)
        logger.info(f"✅ 分红数据增量拉取完成: {dividend_count} 条")

        # Step 2: 因子计算
        logger.info("[2/8] 计算因子...")
        engine = FactorEngine(db)
        df = engine.compute_all(trade_date, top_n=top_n)
        if not df.empty:
            engine.save_factors(df)
        logger.info(f"✅ 因子计算完成: {len(df)} 只股票")

        # Step 3: 同步 PE/PB/换手率到 stock_basic 快照字段
        if not df.empty:
            from app.models.stock import StockBasic as SB
            logger.info("[3/8] 同步估值数据到 stock_basic...")
            for _, row in df.iterrows():
                code = row.get("stock_code")
                if not code:
                    continue
                db.query(SB).filter(SB.stock_code == code).update({
                    "pe_ttm": float(row["stock_pe_ttm"]) if pd.notna(row.get("stock_pe_ttm")) else None,
                    "pb": float(row["stock_pb"]) if pd.notna(row.get("stock_pb")) else None,
                    "turnover_rate": float(row["stock_turnover_rate_5d"]) if pd.notna(row.get("stock_turnover_rate_5d")) else None,
                })
            db.commit()
            logger.info(f"✅ stock_basic 估值数据同步完成: {len(df)} 只股票")

        # Step 4: 标签生成
        logger.info("[4/8] 生成标签...")
        label_gen = LabelGenerator(db)
        labels = label_gen.generate_labels(trade_date)
        logger.info(f"✅ 标签生成完成: {len(labels)} 条")

        # 检查/训练模型
        model_ready = _check_and_train_model(db, trade_date)

        # Step 5: 预测 + 排名
        logger.info("[5/8] 预测...")
        predictor = Predictor(db)
        if model_ready:
            predictions = predictor.predict_daily(trade_date)
        else:
            logger.warning("模型未就绪，跳过预测")
            predictions = pd.DataFrame()
        logger.info(f"✅ 预测完成: {len(predictions)} 只股票")

        logger.info("[6/8] 生成排名...")
        if not predictions.empty:
            top10 = predictor.get_top_n(date.today(), 10)
            from app.models.stock import StockBasic
            from app.models.factor import FactorStore
            from app.models.stock_daily import StockDaily
            from app.models.model_record import ModelRecord

            # 从活跃模型获取特征重要性排名
            model_record = (
                db.query(ModelRecord)
                .filter(ModelRecord.is_active == 1)
                .order_by(ModelRecord.id.desc())
                .first()
            )
            top_candidate_names = []
            if model_record and model_record.feature_importance_json:
                top_features = sorted(
                    model_record.feature_importance_json,
                    key=lambda x: x.get("importance", 0),
                    reverse=True,
                )
                top_candidate_names = [
                    f["feature"] for f in top_features
                    if f.get("feature") and not f["feature"].startswith("macro_")
                ][:20]

            for item in top10:
                stock = db.query(StockBasic).filter(StockBasic.stock_code == item["stock_code"]).first()
                if stock:
                    item["stock_name"] = stock.stock_name
                    item["industry"] = stock.industry

                # 补充总市值
                item["market_cap"] = 0
                from app.models.balancesheet import Balancesheet
                daily = (
                    db.query(StockDaily)
                    .filter(
                        StockDaily.stock_code == item["stock_code"],
                        StockDaily.trade_date == trade_date,
                    )
                    .first()
                )
                bs = (
                    db.query(Balancesheet)
                    .filter(Balancesheet.stock_code == item["stock_code"])
                    .order_by(Balancesheet.end_date.desc())
                    .first()
                )
                if daily and daily.close and bs and bs.cap_stk:
                    total_shares = float(bs.cap_stk)
                    close_val = float(daily.close)
                    item["market_cap"] = round(close_val * total_shares, 2)

                # 补充主力因子
                factor_record = (
                    db.query(FactorStore)
                    .filter(
                        FactorStore.stock_code == item["stock_code"],
                        FactorStore.trade_date == trade_date,
                    )
                    .first()
                )
                if factor_record and top_candidate_names:
                    factor_values = []
                    for col in top_candidate_names:
                        val = getattr(factor_record, col, None)
                        if val is not None:
                            factor_values.append({"name": col, "contribution": float(val)})
                    factor_values.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                    item["top_factors"] = factor_values[:5]
                elif factor_record:
                    factor_cols = [
                        col.name for col in FactorStore.__table__.columns
                        if col.name not in ("id", "stock_code", "trade_date", "created_at")
                        and not col.name.startswith("macro_")
                    ]
                    factor_values = []
                    for col in factor_cols:
                        val = getattr(factor_record, col)
                        if val is not None:
                            factor_values.append({"name": col, "contribution": float(val)})
                    factor_values.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                    item["top_factors"] = factor_values[:5]
                else:
                    item["top_factors"] = []

            ranking_service = RankingService(db)
            ranking_service.save_ranking_snapshot(date.today(), top10)
            logger.info(f"✅ 排名生成完成: {len(top10)} 只股票")
        else:
            logger.info("无预测结果，跳过排名生成")

        # Step 6: 流水线运行完成
        logger.info("[7/8] 流水线运行完成")

    except Exception as e:
        logger.error(f"流水线运行失败: {e}")
        raise
    finally:
        db.close()


def main():
    args = parse_args()

    db = SessionLocal()
    try:
        # 第一步：拉取数据
        dates = run_fetch(args, db)

        # 第二步：判断是否继续跑流水线
        if args.fetch_only:
            logger.info("\n💡 已指定 --fetch-only，仅完成数据拉取。")
            logger.info("   如需运行完整流水线，请执行: python scripts/run_pipeline.py [日期]")
        else:
            # 取第一个交易日作为流水线目标日期
            pipeline_date = dates[0] if dates else datetime.now().strftime("%Y-%m-%d")
            run_pipeline(trade_date=pipeline_date, top_n=args.top, args=args)
            logger.info("\n💡 完整流水线已完成。")
            logger.info("   如需仅拉取数据请使用: python scripts/run_pipeline.py --fetch-only [日期]")

    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
    except Exception as e:
        logger.error(f"❌ 运行异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()