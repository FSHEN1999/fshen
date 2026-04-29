# -*- coding: utf-8 -*-
"""
数据库助手模块 - 集中管理所有数据库查询，使用参数化查询防止SQL注入
"""

from typing import Optional, Any, Dict, List
import logging


class DatabaseHelper:
    """数据库查询助手 - 参数化所有查询，防止SQL注入"""

    @staticmethod
    def get_merchant_id(db, phone: str) -> Optional[str]:
        """根据手机号获取商户ID"""
        sql = "SELECT merchant_id FROM dpu_users WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (phone,))
        except Exception as e:
            logging.error(f"❌ 查询merchant_id失败: {e}")
            return None

    @staticmethod
    def get_application_unique_id(db, merchant_id: str) -> Optional[str]:
        """根据商户ID获取应用ID"""
        sql = "SELECT application_unique_id FROM dpu_application WHERE merchant_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (merchant_id,))
        except Exception as e:
            logging.error(f"❌ 查询application_unique_id失败: {e}")
            return None

    @staticmethod
    def get_preferred_currency(db, merchant_id: str) -> str:
        """根据商户ID获取首选货币（默认USD）"""
        sql = "SELECT prefer_finance_product_currency FROM dpu_users WHERE merchant_id = %s LIMIT 1"
        try:
            result = db.execute_sql_param(sql, (merchant_id,))
            return result if result else "USD"
        except Exception as e:
            logging.error(f"❌ 查询preferred_currency失败: {e}")
            return "USD"

    @staticmethod
    def get_authorization_id(db, merchant_id: str, authorization_party: str = 'SP') -> Optional[str]:
        """根据商户ID获取授权ID"""
        sql = "SELECT authorization_id FROM dpu_auth_token WHERE merchant_id = %s AND authorization_party = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (merchant_id, authorization_party))
        except Exception as e:
            logging.error(f"❌ 查询authorization_id失败: {e}")
            return None

    @staticmethod
    def get_limit_application_id(db, merchant_id: str) -> Optional[str]:
        """根据商户ID获取额度应用ID"""
        sql = "SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (merchant_id,))
        except Exception as e:
            logging.error(f"❌ 查询limit_application_unique_id失败: {e}")
            return None

    @staticmethod
    def get_fund_application_id(db, merchant_id: str) -> Optional[str]:
        """根据商户ID获取基金应用ID"""
        sql = "SELECT fund_application_id FROM dpu_lender_shop_data_transmission WHERE merchant_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (merchant_id,))
        except Exception as e:
            logging.error(f"❌ 查询fund_application_id失败: {e}")
            return None

    @staticmethod
    def get_platform_offer_id(db, selling_partner_id: str) -> Optional[str]:
        """根据selling_partner_id获取平台报价ID"""
        sql = "SELECT platform_offer_id FROM dpu_seller_center.dpu_manual_offer WHERE platform_seller_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (selling_partner_id,))
        except Exception as e:
            logging.error(f"❌ 查询platform_offer_id失败: {e}")
            return None

    @staticmethod
    def get_idempotency_key(db, selling_partner_id: str) -> Optional[str]:
        """根据selling_partner_id获取幂等性密钥"""
        sql = "SELECT idempotency_key FROM dpu_seller_center.dpu_manual_offer WHERE platform_seller_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (selling_partner_id,))
        except Exception as e:
            logging.error(f"❌ 查询idempotency_key失败: {e}")
            return None

    @staticmethod
    def get_loan_id(db, merchant_id: str) -> Optional[str]:
        """根据商户ID获取贷款ID"""
        sql = "SELECT loan_id FROM dpu_drawdown WHERE merchant_id = %s ORDER BY created_at DESC LIMIT 1"
        try:
            return db.execute_sql_param(sql, (merchant_id,))
        except Exception as e:
            logging.error(f"❌ 查询loan_id失败: {e}")
            return None

    @staticmethod
    def batch_get_ids(db, phone: str) -> Dict[str, Optional[str]]:
        """一次性获取常用的多个ID，减少数据库查询"""
        merchant_id = DatabaseHelper.get_merchant_id(db, phone)
        if not merchant_id:
            return {}

        return {
            "merchant_id": merchant_id,
            "application_unique_id": DatabaseHelper.get_application_unique_id(db, merchant_id),
            "preferred_currency": DatabaseHelper.get_preferred_currency(db, merchant_id),
            "authorization_id": DatabaseHelper.get_authorization_id(db, merchant_id),
            "limit_application_id": DatabaseHelper.get_limit_application_id(db, merchant_id),
            "fund_application_id": DatabaseHelper.get_fund_application_id(db, merchant_id),
            "loan_id": DatabaseHelper.get_loan_id(db, merchant_id),
        }
