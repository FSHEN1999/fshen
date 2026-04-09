# -*- coding: utf-8 -*-
"""
测试 webhook_service.py Webhook服务模块
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import requests
from libs.webhook_service import WebhookService, EventType


class TestEventType(unittest.TestCase):
    """EventType枚举测试"""
    
    def test_all_event_types_exist(self):
        """测试所有事件类型都存在"""
        expected_types = [
            "UNDERWRITTEN",
            "APPROVED",
            "PSP_START",
            "PSP_COMPLETED",
            "ESIGN",
            "DISBURSEMENT",
            "INDICATIVE_OFFER"
        ]
        
        for event_name in expected_types:
            self.assertTrue(hasattr(EventType, event_name))
    
    def test_event_type_values(self):
        """测试事件类型的�?""
        self.assertEqual(EventType.UNDERWRITTEN.value, "underwrittenLimit.completed")
        self.assertEqual(EventType.APPROVED.value, "approvedoffer.completed")
        self.assertEqual(EventType.INDICATIVE_OFFER.value, "INDICATIVE-OFFER")


class TestWebhookServiceInitialization(unittest.TestCase):
    """Webhook服务初始化测�?""
    
    def test_webhook_service_creation(self):
        """测试WebhookService对象创建"""
        service = WebhookService("https://test.example.com")
        
        self.assertEqual(service.base_url, "https://test.example.com")
        self.assertEqual(service.default_timeout, 30)
    
    def test_webhook_service_with_different_timeout(self):
        """测试自定义超时时�?""
        service = WebhookService("https://test.example.com")
        service.default_timeout = 60
        
        self.assertEqual(service.default_timeout, 60)


class TestSendUpdateOffer(unittest.TestCase):
    """发送updateOffer测试"""
    
    @patch('libs.webhook_service.requests.post')
    def test_send_update_offer_success(self, mock_post):
        """测试成功发送updateOffer"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_update_offer(
            idempotency_key="test-key-123",
            offer_id="test-offer-456"
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(response)
        self.assertIsNone(error)
        self.assertTrue(mock_post.called)
    
    @patch('libs.webhook_service.requests.post')
    def test_send_update_offer_failure(self, mock_post):
        """测试updateOffer失败"""
        # 模拟失败响应
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "bad request"}'
        mock_post.return_value = mock_response
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_update_offer(
            idempotency_key="test-key-123",
            offer_id="test-offer-456"
        )
        
        self.assertFalse(success)
        self.assertIsNone(response)
        self.assertIsNotNone(error)
        self.assertIn("400", error)
    
    @patch('libs.webhook_service.requests.post')
    def test_send_update_offer_timeout(self, mock_post):
        """测试updateOffer超时"""
        # 模拟超时异常
        mock_post.side_effect = requests.exceptions.Timeout()
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_update_offer(
            idempotency_key="test-key-123",
            offer_id="test-offer-456"
        )
        
        self.assertFalse(success)
        self.assertIsNone(response)
        self.assertIsNotNone(error)
        self.assertIn("超时", error)
    
    @patch('libs.webhook_service.requests.post')
    def test_send_update_offer_exception(self, mock_post):
        """测试updateOffer异常"""
        # 模拟通用异常
        mock_post.side_effect = Exception("Connection error")
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_update_offer(
            idempotency_key="test-key-123",
            offer_id="test-offer-456"
        )
        
        self.assertFalse(success)
        self.assertIsNone(response)
        self.assertIsNotNone(error)


class TestSendSystemEvents(unittest.TestCase):
    """发送系统事件测�?""
    
    @patch('libs.webhook_service.requests.post')
    def test_send_system_events_success(self, mock_post):
        """测试成功发送系统事�?""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_system_events(
            application_id="app-123",
            fund_application_id="fund-456",
            customer_id="cust-789"
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(response)
        self.assertIsNone(error)
    
    @patch('libs.webhook_service.requests.post')
    def test_send_system_events_failure(self, mock_post):
        """测试系统事件发送失�?""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "unauthorized"}'
        mock_post.return_value = mock_response
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_system_events(
            application_id="app-123",
            fund_application_id="fund-456",
            customer_id="cust-789"
        )
        
        self.assertFalse(success)
        self.assertIsNone(response)
        self.assertIsNotNone(error)
    
    @patch('libs.webhook_service.requests.post')
    def test_send_system_events_timeout(self, mock_post):
        """测试系统事件超时"""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        service = WebhookService("https://test.example.com")
        success, response, error = service.send_system_events(
            application_id="app-123",
            fund_application_id="fund-456",
            customer_id="cust-789"
        )
        
        self.assertFalse(success)
        self.assertIsNone(response)
        self.assertIsNotNone(error)
        self.assertIn("超时", error)


class TestWebhookRequestStructure(unittest.TestCase):
    """测试webhook请求结构"""
    
    @patch('libs.webhook_service.requests.post')
    def test_update_offer_request_body(self, mock_post):
        """测试updateOffer请求体结�?""
        service = WebhookService("https://test.example.com")
        service.send_update_offer(
            idempotency_key="key-123",
            offer_id="offer-456",
            send_status="SUCCESS",
            reason=""
        )
        
        # 验证POST被调�?
        self.assertTrue(mock_post.called)
        
        # 获取调用时的参数
        call_args = mock_post.call_args
        json_data = call_args.kwargs.get('json')
        
        # 验证请求体结�?
        self.assertIsNotNone(json_data)
        self.assertEqual(json_data['idempotencyKey'], 'key-123')
        self.assertEqual(json_data['offerId'], 'offer-456')
        self.assertEqual(json_data['sendStatus'], 'SUCCESS')
    
    @patch('libs.webhook_service.requests.post')
    def test_system_events_request_body(self, mock_post):
        """测试系统事件请求体结�?""
        service = WebhookService("https://test.example.com")
        service.send_system_events(
            application_id="app-123",
            fund_application_id="fund-456",
            customer_id="cust-789"
        )
        
        # 验证POST被调�?
        self.assertTrue(mock_post.called)
        
        # 获取调用时的参数
        call_args = mock_post.call_args
        json_data = call_args.kwargs.get('json')
        
        # 验证请求体结�?
        self.assertIsNotNone(json_data)
        self.assertEqual(json_data['applicationUniqueId'], 'app-123')
        self.assertEqual(json_data['eventType'], 'INDICATIVE-OFFER')
        self.assertEqual(json_data['eventData']['applicationId'], 'fund-456')
        self.assertEqual(json_data['eventData']['thirdPartyCustomerId'], 'cust-789')


if __name__ == "__main__":
    unittest.main()
