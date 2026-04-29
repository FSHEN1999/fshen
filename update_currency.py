import pymysql

# 数据库配置（reg环境）
db_config = {
    'host': '18.162.145.173',
    'user': 'dpu_reg',
    'password': 'r4asUYBX3R6LNdp',
    'database': 'dpu_seller_center',
    'port': 3307,
    'charset': 'utf8mb4',
    'connect_timeout': 15,
    'read_timeout': 15,
}

conn = pymysql.connect(**db_config, autocommit=True)
cursor = conn.cursor()

# 更新货币为CNY
phone = '14566331632'  # 替换为实际手机号
cursor.execute("UPDATE dpu_users SET prefer_finance_product_currency = 'CNY' WHERE phone_number = %s", (phone,))

print(f'已更新手机号 {phone} 的偏好融资产品货币为 CNY')

cursor.close()
conn.close()
