# -*- coding: utf-8 -*-
"""
Webhook服务模块 - 统一管理所有webhook请求，支持参数化调用减少重复代码
"""

import logging
import random
import time
import uuid
import requests
from typing import Dict, Optional, Any, Tuple
from enum import Enum

from libs.exceptions import APIRequestError, APITimeoutError, APIResponseError


class EventType(Enum):
    """事件类型枚举"""
    UNDERWRITTEN = "underwrittenLimit.completed"
    APPROVED = "approvedoffer.completed"
    PSP_START = "psp.verification.started"
    PSP_COMPLETED = "psp.verification.completed"
    ESIGN = "esign.completed"
    DISBURSEMENT = "disbursement.completed"
    INDICATIVE_OFFER = "INDICATIVE-OFFER"


class WebhookService:
    """Webhook服务 - 统一处理所有webhook请求"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.default_timeout = 30
        self.default_jwt = (
            "JWS eyJ2ZXIiOiIxLjAiLCJraWQiOiJCQzAwMDAxMTA2NyIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0."
            "eyJzdWIiOiJCQzAwMDAxMTA2NyIsImF1ZCI6IkdCQS1FQ09NTSIsInBheWxvYWRfaGFzaF9hbGciOiJTSEEtMjU2IiwicGF5bG9hZF9oYXNoIjoi"
            "OWFkNjQyZmM4MGY1YmJkZTYwZDFhMmI1ZjJmMTJkNjY4OTJiZGQ4MGVlMzc4ODUzOTE4NTA2MmJkNjFjMzg5YyIsImlhdCI6"
            "MTc2OTA3NjQ4OCwianRpIjoiYjQ1OWJjMWYtZWNkZi00Mjc4LWIwMjMtNTQ2YzM4Y2ZmNWRhIn0.ULI-b7nl8E1n4JXjCR7jAOY1maoUlL5_kBex-FHITC"
            "fVa7VPRPPKRiU4RZhFlGVdRS1sJzGmlce4Gn0nidbWUISI7JzN-94N3GxMuMinVoLi6U_3SIH1a3Ykx4LdSACRL7DC2Jw1kcjKqgzaO-"
            "30TnR4iR1JtwcUPqcmSII8CxoYDFrrMh-Hqwq16fvj92VcgkMQB_TPu0ZezwBus01YLetiA4wCkCk-1Jq4K5E8EImHzDUISAiHyDovQo79t37bTX18"
            "ir0q1MvSqIgCDyMcb7-13REKXDjAE6AJKxprwE6RsrDULc0texMPra2j1PUdIfGGggsBjz0dlHDuaHXyCw"
        )
    
    def send_webhook_notification(self, event_type: EventType, event_data: Dict[str, Any],
                                  message: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        发送标准webhook通知（/dpu-openapi/webhook-notifications）
        
        Args:
            event_type: 事件类型
            event_data: 事件详情数据
            message: 事件消息描述
        
        Returns:
            (成功标志, 响应内容, 错误信息)
        """
        webhook_url = f"{self.base_url}/dpu-openapi/webhook-notifications"
        
        try:
            request_body = {
                "data": {
                    "eventType": event_type.value,
                    "eventId": str(uuid.uuid4()),
                    "eventMessage": message or event_type.value,
                    "enquiryUrl": "https://api.example.com/enquiry",
                    "datetime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "details": event_data
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            logging.info(f"[Webhook] 发送 {event_type.name} 通知到: {webhook_url}")
            
            response = requests.post(webhook_url, json=request_body, headers=headers, 
                                   timeout=self.default_timeout)
            
            if response.status_code == 200:
                logging.info(f"✅ {event_type.name}通知发送成功")
                return True, response.text[:200], None
            else:
                error_msg = f"状态码: {response.status_code}, 响应: {response.text[:200]}"
                logging.error(f"❌ {event_type.name}通知失败 | {error_msg}")
                return False, None, error_msg
        
        except requests.exceptions.Timeout:
            error_msg = f"请求超时 ({self.default_timeout}s)"
            logging.error(f"❌ {event_type.name}通知超时 | {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = str(e)
            logging.error(f"❌ {event_type.name}通知异常: {error_msg}")
            return False, None, error_msg
    
    def send_update_offer(self, idempotency_key: str, offer_id: str, 
                         send_status: str = "SUCCESS", reason: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        发送updateOffer请求 (SP完成后、3PL前)
        
        Args:
            idempotency_key: 幂等性密钥
            offer_id: 报价ID
            send_status: 发送状态，默认为SUCCESS
            reason: 失败原因（可选）
        
        Returns:
            (成功标志, 响应内容, 错误信息)
        """
        webhook_url = f"{self.base_url}/dpu-auth/amazon-sp/updateOffer"
        
        try:
            request_body = {
                "idempotencyKey": idempotency_key,
                "sendStatus": send_status,
                "offerId": offer_id,
                "reason": reason
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            logging.info(f"[Webhook] 发送updateOffer请求到: {webhook_url}")
            logging.info(f"   idempotencyKey: {idempotency_key}")
            logging.info(f"   offerId: {offer_id}")
            
            response = requests.post(webhook_url, json=request_body, headers=headers,
                                   timeout=self.default_timeout)
            
            if response.status_code == 200:
                logging.info(f"✅ updateOffer请求成功")
                return True, response.text[:200], None
            else:
                error_msg = f"状态码: {response.status_code}, 响应: {response.text[:200]}"
                logging.error(f"❌ updateOffer请求失败 | {error_msg}")
                return False, None, error_msg
        
        except requests.exceptions.Timeout:
            error_msg = f"请求超时 ({self.default_timeout}s)"
            logging.error(f"❌ updateOffer请求超时 | {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = str(e)
            logging.error(f"❌ updateOffer请求异常: {error_msg}")
            return False, None, error_msg
    
    def send_system_events(self, application_id: str, fund_application_id: str,
                          customer_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        发送系统事件通知 (INDICATIVE-OFFER)
        
        Args:
            application_id: 应用ID
            fund_application_id: 基金应用ID
            customer_id: 客户ID
        
        Returns:
            (成功标志, 响应内容, 错误信息)
        """
        webhook_url = f"{self.base_url}/dpu-openapi/notification/system-events"
        
        try:
            # 生成唯一的请求ID
            correlation_id = str(uuid.uuid4()).replace("-", "")[:32]
            idempotency_key = str(uuid.uuid4())
            trust_token = "".join([random.choice("0123456789ABCDEF") for _ in range(16)])
            
            request_body = {
                "applicationUniqueId": application_id,
                "eventType": "INDICATIVE-OFFER",
                "eventReceiver": "dpu",
                "eventData": {
                    "thirdPartyCustomerId": customer_id,
                    "applicationId": fund_application_id,
                    "eventTime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "errorCode": "",
                    "errorMessage": ""
                }
            }
            
            headers = {
                "Authorization": self.default_jwt,
                "X-HSBC-Request-Correlation-Id": correlation_id,
                "X-HSBC-E2E-Trust-Token": trust_token,
                "X-HSBC-Request-Idempotency-Key": idempotency_key,
                "X-HSBC-PROFILEID": "DPUSIT-B2B-P-2025-ACTIVE",
                "Accept": "*/*",
                "Funder-Resource": "HSBC",
                "Content-Type": "application/json"
            }
            
            logging.info(f"[Webhook] 发送INDICATIVE-OFFER通知到: {webhook_url}")
            logging.info(f"   applicationUniqueId: {application_id}")
            logging.info(f"   fundApplicationId: {fund_application_id}")
            logging.info(f"   thirdPartyCustomerId: {customer_id}")
            
            response = requests.post(webhook_url, json=request_body, headers=headers,
                                   timeout=self.default_timeout)
            
            if response.status_code == 200:
                logging.info(f"✅ INDICATIVE-OFFER通知发送成功")
                return True, response.text[:200], None
            else:
                error_msg = f"状态码: {response.status_code}, 响应: {response.text[:200]}"
                logging.error(f"❌ INDICATIVE-OFFER通知失败 | {error_msg}")
                return False, None, error_msg
        
        except requests.exceptions.Timeout:
            error_msg = f"请求超时 ({self.default_timeout}s)"
            logging.error(f"❌ INDICATIVE-OFFER通知超时 | {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = str(e)
            logging.error(f"❌ INDICATIVE-OFFER通知异常: {error_msg}")
            return False, None, error_msg
