"""数据库迁移：为 prediction 和 ranking_snapshot 表添加 1日收益率 字段"""
import pymysql

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='agu_user',
    password='agu123',
    database='agu_quant'
)

cursor = conn.cursor()

try:
    # prediction 表
    cursor.execute("""
        ALTER TABLE prediction
        ADD COLUMN predicted_return_1d DECIMAL(12,6) DEFAULT NULL
        COMMENT '预测1日收益率' AFTER predicted_return
    """)
    print("✅ prediction 表 added: predicted_return_1d")

    cursor.execute("""
        ALTER TABLE prediction
        ADD COLUMN confidence_1d DECIMAL(6,4) DEFAULT NULL
        COMMENT '预测置信度(1日)' AFTER confidence
    """)
    print("✅ prediction 表 added: confidence_1d")

    # ranking_snapshot 表
    cursor.execute("""
        ALTER TABLE ranking_snapshot
        ADD COLUMN predicted_return_1d DECIMAL(12,6) DEFAULT NULL
        COMMENT '预测1日收益率' AFTER predicted_return
    """)
    print("✅ ranking_snapshot 表 added: predicted_return_1d")

    conn.commit()
    print("🎉 所有迁移完成！")

except Exception as e:
    conn.rollback()
    print(f"❌ 迁移失败: {e}")

finally:
    cursor.close()
    conn.close()