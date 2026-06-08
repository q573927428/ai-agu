"""
预测结果验证脚本 — 对比预测收益率 vs 实际收益率（次日预测）

用法:
  python scripts/verify_predictions.py                    # 验证所有预测记录
  python scripts/verify_predictions.py --days 20          # 验证最近20条预测
  python scripts/verify_predictions.py --stock 000001     # 验证指定股票
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.utils.db_utils import SessionLocal
from app.models.prediction import Prediction
from app.models.stock_daily import StockDaily
from app.models.stock import StockBasic


def compute_actual_returns(db: Session, predictions: list) -> list:
    """
    对每条预测记录，从 stock_daily 中查找次日涨跌幅，计算实际收益率
    """
    # 按股票代码分组，批量查询减少SQL次数
    stock_codes = set(p.stock_code for p in predictions)
    
    # 获取每只股票的所有收盘价（范围涵盖所有预测的日期范围）
    min_date = min(p.predict_date for p in predictions)
    max_date = max(
        p.predict_date + timedelta(days=2)  # 至少T+1
        for p in predictions
    ) if predictions else date.today()

    # 批量查询所有股票的日行情
    rows = (
        db.query(StockDaily.stock_code, StockDaily.trade_date, StockDaily.close, StockDaily.pct_chg)
        .filter(
            StockDaily.stock_code.in_(stock_codes),
            StockDaily.trade_date.between(min_date, max_date),
        )
        .order_by(StockDaily.stock_code, StockDaily.trade_date)
        .all()
    )

    # 构建 {stock_code: [(trade_date, close, pct_chg), ...]} 映射
    stock_daily_map: dict[str, list] = {}
    for r in rows:
        stock_daily_map.setdefault(r.stock_code, []).append((
            r.trade_date, 
            float(r.close) if r.close else None,
            float(r.pct_chg) if r.pct_chg else None,
        ))

    # 对每条预测计算实际收益率
    results = []
    for p in predictions:
        daily_list = stock_daily_map.get(p.stock_code, [])
        # 查找预测日次日涨跌幅
        next_day_pct = None
        
        for td, _close, pct in daily_list:
            if td == p.predict_date + timedelta(days=1):
                next_day_pct = pct  # 直接使用涨跌幅（百分数）

        # 实际次日收益率（百分数表示，如 5.0 = 5%）
        actual_return = float(next_day_pct) if next_day_pct is not None else None

        # 转换预测值为百分数（prediction 表存的是小数，如 0.05 = 5% → 转为 5.0）
        pred_return = float(p.predicted_return) * 100 if p.predicted_return is not None else None
        results.append({
            "stock_code": p.stock_code,
            "predict_date": p.predict_date,
            "target_date": p.target_date,
            "predicted_return": pred_return,
            "actual_return": actual_return,
            "confidence": float(p.confidence) if p.confidence else None,
        })

    return results


def compute_metrics(results: list) -> dict:
    """
    计算验证指标（次日收益率）
    """
    df = pd.DataFrame(results)

    metrics = {}

    # === 次日收益率验证 ===
    valid = df.dropna(subset=["predicted_return", "actual_return"])
    if len(valid) > 0:
        # 预测方向准确率（同涨同跌）
        direction_correct = (
            ((valid["predicted_return"] > 0) & (valid["actual_return"] > 0)) |
            ((valid["predicted_return"] < 0) & (valid["actual_return"] < 0))
        ).sum()
        metrics["direction_accuracy"] = round(direction_correct / len(valid), 4)
        metrics["total_samples"] = len(valid)
        metrics["direction_correct"] = int(direction_correct)

        # Spearman 秩相关（排名相关性）
        pred_rank = valid["predicted_return"].rank()
        actual_rank = valid["actual_return"].rank()
        rank_corr = pred_rank.corr(actual_rank)
        metrics["rank_correlation"] = round(rank_corr, 4) if not pd.isna(rank_corr) else None

        # Pearson 相关系数
        pearson_corr = valid["predicted_return"].corr(valid["actual_return"])
        metrics["pearson_correlation"] = round(pearson_corr, 4) if not pd.isna(pearson_corr) else None

        # 平均绝对误差
        mae = (valid["predicted_return"] - valid["actual_return"]).abs().mean()
        metrics["mae_pct"] = round(mae, 2)

        # 预测均值 vs 实际均值
        metrics["pred_mean"] = round(valid["predicted_return"].mean(), 2)
        metrics["actual_mean"] = round(valid["actual_return"].mean(), 2)

    return metrics, df


def print_summary(metrics: dict, df: pd.DataFrame, stock_filter: str = None):
    """打印验证汇总"""
    title = "🎯 预测结果验证报告"
    if stock_filter:
        title += f" — 股票 {stock_filter}"

    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

    print(f"\n📊 总预测记录数: {len(df)}")
    print(f"  有实际次日收益可验证: {metrics.get('total_samples', 0)} 条")

    # 次日预测
    if 'total_samples' in metrics and metrics['total_samples'] > 0:
        print(f"\n📈 【次日收益率预测验证】")
        print(f"  ✅ 方向准确率: {metrics['direction_accuracy']*100:.2f}%")
        print(f"     （{metrics['direction_correct']}/{metrics['total_samples']} 次方向判断正确）")
        print(f"  📐 Spearman秩相关: {metrics.get('rank_correlation', 'N/A')}")
        print(f"  📐 Pearson相关:    {metrics.get('pearson_correlation', 'N/A')}")
        print(f"  📉 平均绝对误差(MAE): {metrics.get('mae_pct', 'N/A')}%")
        print(f"  📊 预测平均: {metrics.get('pred_mean', 'N/A')}% | 实际平均: {metrics.get('actual_mean', 'N/A')}%")

    # 打印部分详细记录
    print(f"\n📋 详细记录（前20条）:")
    print(f"  {'股票代码':<10} {'预测日期':<12} {'预测次日%':<12} {'实际次日%':<12} {'准确?':<6}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")
    
    # 决定排序方式：如果有股票过滤按日期，否则按预测日期倒序
    display_df = df if len(df) <= 20 else df.head(20)
    for _, r in display_df.iterrows():
        pred = r.get("predicted_return")
        actual = r.get("actual_return")
        
        # 判断方向是否准确
        correct = ""
        if pred is not None and actual is not None:
            if (pred > 0 and actual > 0) or (pred < 0 and actual < 0):
                correct = "✅"
            else:
                correct = "❌"
        
        print(f"  {r['stock_code']:<10} {str(r['predict_date']):<12} "
              f"{f'{pred:+.2f}' if pred is not None else 'N/A':<12} "
              f"{f'{actual:+.2f}' if actual is not None else 'N/A':<12} "
              f"{correct:<6}")

    # TOP10 选出预测涨幅最大的10只，看实际表现
    if 'predicted_return' in df.columns:
        top10 = df.nlargest(10, "predicted_return").dropna(subset=["actual_return"])
        if len(top10) > 0:
            print(f"\n🏆 TOP10（预测次日涨幅最大）实际表现:")
            top10_actual_mean = top10["actual_return"].mean()
            top10_pred_mean = top10["predicted_return"].mean()
            print(f"  预测均涨幅: {top10_pred_mean:+.2f}% → 实际均涨幅: {top10_actual_mean:+.2f}%")
            # 其中上涨比例
            win_count = (top10["actual_return"] > 0).sum()
            print(f"  上涨: {win_count}/{len(top10)}")

    print("=" * 60)
    print()


def verify_all(db: Session):
    """验证所有预测记录"""
    predictions = db.query(Prediction).order_by(Prediction.predict_date.desc()).all()
    logger.info(f"查询到 {len(predictions)} 条预测记录")
    return predictions


def verify_recent(db: Session, days: int):
    """验证最近N个预测日期的记录"""
    subquery = (
        db.query(Prediction.predict_date)
        .distinct()
        .order_by(Prediction.predict_date.desc())
        .limit(days)
        .subquery()
    )
    predictions = (
        db.query(Prediction)
        .filter(Prediction.predict_date.in_(subquery))
        .order_by(Prediction.predict_date.desc(), Prediction.stock_code)
        .all()
    )
    logger.info(f"查询到最近{days}个预测日期的 {len(predictions)} 条记录")
    return predictions


def verify_stock(db: Session, stock_code: str):
    """验证指定股票的所有预测"""
    predictions = (
        db.query(Prediction)
        .filter(Prediction.stock_code == stock_code)
        .order_by(Prediction.predict_date.desc())
        .all()
    )
    logger.info(f"查询到股票 {stock_code} 的 {len(predictions)} 条预测记录")
    
    # 补上股票名称
    stock = db.query(StockBasic).filter(StockBasic.stock_code == stock_code).first()
    if stock:
        print(f"\n📌 股票: {stock.stock_name} ({stock.stock_code})")
    return predictions


def main():
    parser = argparse.ArgumentParser(description="验证预测结果 vs 实际收益率（次日）")
    parser.add_argument("--days", type=int, default=0, help="验证最近N个预测日期的记录")
    parser.add_argument("--stock", type=str, default="", help="验证指定股票代码")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.stock:
            predictions = verify_stock(db, args.stock)
        elif args.days > 0:
            predictions = verify_recent(db, args.days)
        else:
            predictions = verify_all(db)

        if not predictions:
            logger.warning("没有找到预测记录")
            return

        # 计算实际收益率
        results = compute_actual_returns(db, predictions)
        logger.info(f"验证计算完成: {len(results)} 条")

        # 计算指标并打印
        metrics, df = compute_metrics(results)
        print_summary(metrics, df, stock_filter=args.stock)

        # 保存 CSV
        output_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            f"prediction_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        logger.info(f"详细结果已保存到: {output_file}")

    finally:
        db.close()


if __name__ == "__main__":
    main()