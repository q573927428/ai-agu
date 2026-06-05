import pymysql
conn = pymysql.connect(host='localhost', user='agu_user', password='agu123', database='agu_quant')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM stock_basic')
count = cur.fetchone()[0]
print(f'stock_basic 表记录数: {count}')
if count > 0:
    cur.execute('SELECT stock_code, stock_name FROM stock_basic LIMIT 5')
    for r in cur.fetchall():
        print(f'  {r[0]} {r[1]}')
conn.close()