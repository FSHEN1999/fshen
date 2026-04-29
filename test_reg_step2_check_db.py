# -*- coding: utf-8 -*-
"""
步骤 2: 查询数据库确认注册账号的数据
"""
import pymysql
import logging

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# REG 环境数据库配置
DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4"
}

# 测试账号
PHONE_NUMBER = "18612898782"


def query_database():
    """查询数据库"""
    log.info("="*60)
    log.info("查询 REG 环境数据库")
    log.info("="*60)

    try:
        # 连接数据库
        log.info(f"连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        log.info("✅ 数据库连接成功")

        # 查询 1: dpu_users 表
        log.info(f"\n{'='*60}")
        log.info("查询 1: dpu_users 表")
        log.info(f"{'='*60}")

        sql = f"SELECT * FROM dpu_users WHERE phone_number='{PHONE_NUMBER}' LIMIT 1"
        log.info(f"SQL: {sql}")
        cursor.execute(sql)
        user = cursor.fetchone()

        if user:
            log.info("✅ 找到用户记录:")
            for key, value in user.items():
                log.info(f"  {key}: {value}")
            merchant_id = user.get('merchant_id')
        else:
            log.error("❌ 未找到用户记录")
            return

        # 查询 2: dpu_application 表
        log.info(f"\n{'='*60}")
        log.info("查询 2: dpu_application 表")
        log.info(f"{'='*60}")

        sql = f"SELECT * FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        log.info(f"SQL: {sql}")
        cursor.execute(sql)
        application = cursor.fetchone()

        if application:
            log.info("✅ 找到 application 记录:")
            for key, value in application.items():
                log.info(f"  {key}: {value}")
        else:
            log.warning("⚠️ 未找到 application 记录")

        # 查询 3: dpu_merchant_account_limit 表
        log.info(f"\n{'='*60}")
        log.info("查询 3: dpu_merchant_account_limit 表")
        log.info(f"{'='*60}")

        sql = f"SELECT * FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}' LIMIT 1"
        log.info(f"SQL: {sql}")
        cursor.execute(sql)
        account_limit = cursor.fetchone()

        if account_limit:
            log.info("✅ 找到 account_limit 记录:")
            for key, value in account_limit.items():
                log.info(f"  {key}: {value}")
        else:
            log.warning("⚠️ 未找到 account_limit 记录")

        # 查询 4: dpu_credit_offer 表
        log.info(f"\n{'='*60}")
        log.info("查询 4: dpu_credit_offer 表")
        log.info(f"{'='*60}")

        sql = f"SELECT * FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1"
        log.info(f"SQL: {sql}")
        cursor.execute(sql)
        credit_offer = cursor.fetchone()

        if credit_offer:
            log.info("✅ 找到 credit_offer 记录:")
            for key, value in credit_offer.items():
                log.info(f"  {key}: {value}")
        else:
            log.warning("⚠️ 未找到 credit_offer 记录")

        # 查询 5: dpu_shops 表
        log.info(f"\n{'='*60}")
        log.info("查询 5: dpu_shops 表")
        log.info(f"{'='*60}")

        sql = f"SELECT * FROM dpu_shops WHERE merchant_id='{merchant_id}' LIMIT 5"
        log.info(f"SQL: {sql}")
        cursor.execute(sql)
        shops = cursor.fetchall()

        if shops:
            log.info(f"✅ 找到 {len(shops)} 条 shops 记录:")
            for idx, shop in enumerate(shops, 1):
                log.info(f"\n  Shop {idx}:")
                for key, value in shop.items():
                    log.info(f"    {key}: {value}")
        else:
            log.warning("⚠️ 未找到 shops 记录")

        # 总结
        log.info(f"\n{'='*60}")
        log.info("数据总结")
        log.info(f"{'='*60}")
        log.info(f"merchant_id: {merchant_id}")
        log.info(f"application 记录: {'✅ 存在' if application else '❌ 不存在'}")
        log.info(f"account_limit 记录: {'✅ 存在' if account_limit else '❌ 不存在'}")
        log.info(f"credit_offer 记录: {'✅ 存在' if credit_offer else '❌ 不存在'}")
        log.info(f"shops 记录: {'✅ 存在 ' + str(len(shops)) + ' 条' if shops else '❌ 不存在'}")

        # 关闭连接
        cursor.close()
        conn.close()
        log.info("\n✅ 数据库查询完成")

    except Exception as e:
        log.error(f"❌ 数据库查询失败: {e}")


if __name__ == "__main__":
    query_database()
