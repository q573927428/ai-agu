import pymysql
conn = pymysql.connect(host='localhost', user='agu_user', password='agu123', database='agu_quant')
cur = conn.cursor()
cur.execute('SELECT COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM factor_store')
row = cur.fetchone()
print(f"factor_store: count={row[0]} min={row[1]} max={row[2]} distinct_dates={row[3]}")

cur.execute('SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM stock_daily')
row = cur.fetchone()
print(f"stock_daily: count={row[0]} distinct_dates={row[1]} min={row[2]} max={row[3]}")

cur.execute('SELECT COUNT(*) FROM model_record')
row = cur.fetchone()
print(f"model_record: count={row[0]}")

cur.execute('SELECT COUNT(*) FROM prediction')
row = cur.fetchone()
print(f"prediction: count={row[0]}")

conn.close()