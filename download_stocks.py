# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts

# ==========================
# 配置
# ==========================

TOKEN = "8debab30cfb89a1c342431660c306757f55352bd67af2a46dd4a280d"

DB_PATH = "stock_daily.db"

STOCKS = [
    "000001.SZ",  # 平安银行
    "600519.SH",  # 贵州茅台
]

# 最近5年
START_DATE = (
    datetime.now() - timedelta(days=365 * 5)
).strftime("%Y%m%d")

END_DATE = datetime.now().strftime("%Y%m%d")


# ==========================
# 初始化
# ==========================

ts.set_token(TOKEN)
pro = ts.pro_api()


def create_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS stock_daily (
        ts_code TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        vol REAL,
        amount REAL,
        PRIMARY KEY (ts_code, trade_date)
    )
    """)

    conn.commit()


def download_stock(ts_code):
    print(f"下载 {ts_code}")

    df = pro.daily(
        ts_code=ts_code,
        start_date=START_DATE,
        end_date=END_DATE
    )

    if df.empty:
        print(f"{ts_code} 无数据")
        return None

    df = df[
        [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "amount"
        ]
    ]

    return df


def save_stock(conn, df):
    sql = """
    INSERT OR REPLACE INTO stock_daily
    (
        ts_code,
        trade_date,
        open,
        high,
        low,
        close,
        vol,
        amount
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    conn.executemany(
        sql,
        df.values.tolist()
    )

    conn.commit()


def main():

    conn = sqlite3.connect(DB_PATH)

    create_table(conn)

    total_rows = 0

    for stock in STOCKS:

        try:
            df = download_stock(stock)

            if df is not None:

                save_stock(conn, df)

                count = len(df)

                total_rows += count

                print(
                    f"{stock} 保存成功 {count} 条"
                )

        except Exception as e:

            print(
                f"{stock} 下载失败: {e}"
            )

    conn.close()

    print(
        f"\n完成，总记录数: {total_rows}"
    )


if __name__ == "__main__":
    main()