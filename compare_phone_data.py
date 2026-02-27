# -*- coding: utf-8 -*-
"""
比较两个手机号在迁移相关表中的数据差异
"""
import pymysql
from pymysql.constants import CLIENT
import json
from typing import Dict, List, Any, Optional

# 数据库配置
DB_CONFIG = {
    "host": "aurora-dpu-sit.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
    "user": "dpu_sit",
    "password": "20250818dpu_sit",
    "database": "dpu_seller_center",
    "port": 3306,
    "charset": "utf8mb4",
    "connect_timeout": 1500,
    "read_timeout": 15,
}

# 迁移涉及的主要表清单
MIGRATION_TABLES = [
    # 用户和授权相关
    ("dpu_users", "phone_number"),
    ("dpu_auth_token", "merchant_id"),

    # 店铺和账户相关
    ("dpu_shops", "merchant_id"),
    ("dpu_merchant_account_limit", "merchant_id"),

    # 申请和流程相关
    ("dpu_application", "merchant_id"),
    ("dpu_limit_application", "merchant_id"),
    ("dpu_limit_application_account", "merchant_id"),
    ("dpu_credit_offer", "merchant_id"),

    # 实体和自然人相关
    ("dpu_entity", "merchant_id"),
    ("dpu_nature_person", "merchant_id"),
    ("dpu_nature_person_documents", "merchant_id"),

    # 额度相关
    ("dpu_merchants_limit", "merchant_id"),

    # 银行账户相关
    ("dpu_bank_account", "merchant_id"),

    # 事件相关
    ("dpu_notify_event_dependency", "biz_id"),
    ("dpu_notify_event", "biz_id"),

    # 放款和还款相关
    ("dpu_drawdown", "merchant_id"),
    ("dpu_repayment", "merchant_id"),
]


class DatabaseComparator:
    """数据库比较器"""

    def __init__(self, config: Dict):
        self.config = config
        self.conn = None
        self.cursor = None

    def connect(self):
        """连接数据库"""
        self.conn = pymysql.connect(**self.config, autocommit=True, client_flag=CLIENT.INTERACTIVE)
        self.cursor = self.conn.cursor()

    def close(self):
        """关闭连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def get_merchant_id(self, phone_number: str) -> Optional[str]:
        """根据手机号获取merchant_id"""
        sql = f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone_number}' ORDER BY created_at DESC LIMIT 1"
        self.cursor.execute(sql)
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_table_columns(self, table_name: str) -> List[str]:
        """获取表的所有列名"""
        sql = f"SHOW COLUMNS FROM {table_name}"
        self.cursor.execute(sql)
        return [row[0] for row in self.cursor.fetchall()]

    def get_table_data(self, table_name: str, phone_number: str, merchant_id: str) -> List[Dict[str, Any]]:
        """获取表中指定手机号/merchant_id的所有数据"""
        columns = self.get_table_columns(table_name)

        # 根据表类型确定查询条件
        if table_name == "dpu_users":
            where_clause = f"phone_number = '{phone_number}'"
        elif table_name in ("dpu_notify_event_dependency", "dpu_notify_event"):
            # 这两个表用biz_id查询，需要先获取application_unique_id
            sql = f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1"
            self.cursor.execute(sql)
            app_result = self.cursor.fetchone()
            if not app_result:
                return []
            biz_id = app_result[0]
            where_clause = f"biz_id = '{biz_id}'"
        else:
            where_clause = f"merchant_id = '{merchant_id}'"

        sql = f"SELECT * FROM {table_name} WHERE {where_clause}"
        self.cursor.execute(sql)
        results = self.cursor.fetchall()

        return [dict(zip(columns, row)) for row in results]

    def get_row_count(self, table_name: str, phone_number: str, merchant_id: str) -> int:
        """获取表中指定手机号/merchant_id的记录数量"""
        if table_name == "dpu_users":
            where_clause = f"phone_number = '{phone_number}'"
        elif table_name in ("dpu_notify_event_dependency", "dpu_notify_event"):
            sql = f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1"
            self.cursor.execute(sql)
            app_result = self.cursor.fetchone()
            if not app_result:
                return 0
            biz_id = app_result[0]
            where_clause = f"biz_id = '{biz_id}'"
        else:
            where_clause = f"merchant_id = '{merchant_id}'"

        sql = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
        self.cursor.execute(sql)
        return self.cursor.fetchone()[0]

    def compare_phones(self, phone1: str, phone2: str) -> Dict[str, Any]:
        """比较两个手机号的数据"""
        # 获取merchant_id
        merchant_id_1 = self.get_merchant_id(phone1)
        merchant_id_2 = self.get_merchant_id(phone2)

        result = {
            "phone1": phone1,
            "phone2": phone2,
            "merchant_id_1": merchant_id_1,
            "merchant_id_2": merchant_id_2,
            "table_comparison": {}
        }

        for table_name, _ in MIGRATION_TABLES:
            count1 = self.get_row_count(table_name, phone1, merchant_id_1) if merchant_id_1 else 0
            count2 = self.get_row_count(table_name, phone2, merchant_id_2) if merchant_id_2 else 0

            comparison = {
                "table": table_name,
                "phone1_count": count1,
                "phone2_count": count2,
                "difference": count1 - count2,
                "status": "相同" if count1 == count2 else "不同"
            }

            # 如果记录数不同，获取详细数据
            if count1 != count2:
                comparison["phone1_data"] = self.get_table_data(table_name, phone1, merchant_id_1) if merchant_id_1 else []
                comparison["phone2_data"] = self.get_table_data(table_name, phone2, merchant_id_2) if merchant_id_2 else []

            result["table_comparison"][table_name] = comparison

        return result

    def print_comparison(self, comparison: Dict[str, Any]):
        """打印比较结果"""
        print("\n" + "=" * 80)
        print(f"数据比较报告")
        print("=" * 80)
        print(f"手机号1: {comparison['phone1']}")
        print(f"Merchant ID 1: {comparison['merchant_id_1']}")
        print(f"手机号2: {comparison['phone2']}")
        print(f"Merchant ID 2: {comparison['merchant_id_2']}")
        print("=" * 80)

        print("\n{:<40} {:>10} {:>10} {:>10} {:<10}".format(
            "表名", "手机号1", "手机号2", "差值", "状态"
        ))
        print("-" * 80)

        different_tables = []
        for table_name, comp in comparison["table_comparison"].items():
            print("{:<40} {:>10} {:>10} {:>10} {:<10}".format(
                table_name,
                comp["phone1_count"],
                comp["phone2_count"],
                comp["difference"],
                comp["status"]
            ))
            if comp["status"] != "相同":
                different_tables.append(table_name)

        print("-" * 80)

        if different_tables:
            print(f"\n发现 {len(different_tables)} 个表存在数据差异:")
            for table in different_tables:
                print(f"  - {table}")
        else:
            print("\n所有表的记录数均相同")

        print("=" * 80)


def main():
    """主函数"""
    phone1 = "18211795038"
    phone2 = "18258603402"

    comparator = DatabaseComparator(DB_CONFIG)

    try:
        comparator.connect()
        print("数据库连接成功")

        comparison = comparator.compare_phones(phone1, phone2)
        comparator.print_comparison(comparison)

        # 保存详细结果到JSON文件
        with open("phone_comparison_result.json", "w", encoding="utf-8") as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2, default=str)
        print("\n详细结果已保存到 phone_comparison_result.json")

    finally:
        comparator.close()
        print("\n数据库连接已关闭")


if __name__ == "__main__":
    main()