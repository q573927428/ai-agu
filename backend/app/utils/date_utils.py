"""交易日历工具"""
from datetime import datetime, timedelta
from typing import Optional


# A股常见节假日（可扩展）
HOLIDAYS = {
    "2026-01-01", "2026-01-02",  # 元旦
    "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21",  # 春节
    "2026-04-04", "2026-04-05", "2026-04-06",  # 清明
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",  # 劳动节
    "2026-06-12", "2026-06-13", "2026-06-14",  # 端午
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",  # 国庆
    "2026-10-08",
}


def is_trade_day(date: datetime) -> bool:
    """判断是否为交易日（周一到周五，非节假日）"""
    if date.weekday() >= 5:  # 周六日
        return False
    date_str = date.strftime("%Y-%m-%d")
    return date_str not in HOLIDAYS


def get_latest_trade_day(date: Optional[datetime] = None) -> datetime:
    """获取最近的一个交易日"""
    if date is None:
        date = datetime.now()

    # 如果是当天且还没收盘（15:00前），取前一个交易日
    if date.hour < 15:
        date = date - timedelta(days=1)

    while not is_trade_day(date):
        date = date - timedelta(days=1)

    return date


def get_next_trade_day(date: datetime) -> datetime:
    """获取下一个交易日"""
    date = date + timedelta(days=1)
    while not is_trade_day(date):
        date = date + timedelta(days=1)
    return date


def get_next_n_trade_days(date: datetime, n: int) -> list:
    """获取未来N个交易日列表"""
    trade_days = []
    current = date + timedelta(days=1)
    while len(trade_days) < n:
        if is_trade_day(current):
            trade_days.append(current)
        current += timedelta(days=1)
    return trade_days


def get_previous_n_trade_days(date: datetime, n: int) -> list:
    """获取过去N个交易日列表"""
    trade_days = []
    current = date
    while len(trade_days) < n:
        if is_trade_day(current):
            trade_days.append(current)
        current -= timedelta(days=1)
    return trade_days
