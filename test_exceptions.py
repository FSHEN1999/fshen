# -*- coding: utf-8 -*-
"""
测试 exceptions.py 自定义异常模块
"""

import unittest
from libs.exceptions import (
    AutomationException,
    ElementTimeoutError, ElementClickError, ElementInputError,
    DatabaseException, DatabaseQueryError,
    APIException, APIRequestError, APITimeoutError, APIResponseError,
    FileException, FileReadError, FileWriteError,
    BrowserException, BrowserProcessError, BrowserConnectionError,
    ValidationException, ValidationError, DataValidationError
)


class TestExceptionInheritance(unittest.TestCase):
    """测试异常继承关系"""
    
    def test_element_timeout_error_inheritance(self):
        """测试ElementTimeoutError继承自UIElementException"""
        error = ElementTimeoutError("元素加载超时")
        self.assertIsInstance(error, AutomationException)
        self.assertIsInstance(error, Exception)
    
    def test_database_exception_inheritance(self):
        """测试DatabaseException继承关系"""
        error = DatabaseQueryError("查询失败")
        self.assertIsInstance(error, DatabaseException)
        self.assertIsInstance(error, AutomationException)
    
    def test_api_exception_inheritance(self):
        """测试APIException继承关系"""
        error = APITimeoutError("请求超时")
        self.assertIsInstance(error, APIException)
        self.assertIsInstance(error, AutomationException)
    
    def test_file_exception_inheritance(self):
        """测试FileException继承关系"""
        error = FileReadError("文件读取失败")
        self.assertIsInstance(error, FileException)
        self.assertIsInstance(error, AutomationException)
    
    def test_browser_exception_inheritance(self):
        """测试BrowserException继承关系"""
        error = BrowserProcessError("浏览器进程异常")
        self.assertIsInstance(error, BrowserException)
        self.assertIsInstance(error, AutomationException)
    
    def test_validation_exception_inheritance(self):
        """测试ValidationException继承关系"""
        error = DataValidationError("数据验证失败")
        self.assertIsInstance(error, ValidationException)
        self.assertIsInstance(error, AutomationException)


class TestExceptionMessages(unittest.TestCase):
    """测试异常消息"""
    
    def test_exception_message(self):
        """测试异常消息保留"""
        message = "这是一个测试消息"
        error = ElementTimeoutError(message)
        self.assertEqual(str(error), message)
    
    def test_exception_message_with_from(self):
        """测试异常链接"""
        try:
            original_error = ValueError("原始错误")
            raise ElementClickError("点击失败") from original_error
        except ElementClickError as e:
            self.assertIsNotNone(e.__cause__)
            self.assertIsInstance(e.__cause__, ValueError)


class TestExceptionCatching(unittest.TestCase):
    """测试异常捕获"""
    
    def test_catch_specific_exception(self):
        """测试捕获特定异常"""
        try:
            raise ElementTimeoutError("元素超时")
        except ElementTimeoutError as e:
            self.assertEqual(str(e), "元素超时")
            caught = True
        
        self.assertTrue(caught)
    
    def test_catch_parent_exception(self):
        """测试捕获父类异常"""
        try:
            raise ElementTimeoutError("元素超时")
        except AutomationException as e:
            self.assertEqual(str(e), "元素超时")
            caught = True
        
        self.assertTrue(caught)
    
    def test_different_exceptions_separate_handling(self):
        """测试不同异常分别处理"""
        exceptions_caught = []
        
        for error_class, message in [
            (ElementTimeoutError, "UI元素超时"),
            (DatabaseQueryError, "数据库查询失败"),
            (APITimeoutError, "API请求超时")
        ]:
            try:
                raise error_class(message)
            except ElementTimeoutError:
                exceptions_caught.append("ui_timeout")
            except DatabaseQueryError:
                exceptions_caught.append("db_query")
            except APITimeoutError:
                exceptions_caught.append("api_timeout")
        
        self.assertEqual(exceptions_caught, ["ui_timeout", "db_query", "api_timeout"])


class TestAllExceptionsExist(unittest.TestCase):
    """测试所有异常类都存在"""
    
    def test_all_exception_classes(self):
        """测试所有14个异常类都可以被实例化"""
        exceptions_to_test = [
            ElementTimeoutError,
            ElementClickError,
            ElementInputError,
            DatabaseQueryError,
            DatabaseException,
            APIRequestError,
            APITimeoutError,
            APIResponseError,
            FileReadError,
            FileWriteError,
            FileException,
            BrowserProcessError,
            BrowserConnectionError,
            DataValidationError
        ]
        
        for exception_class in exceptions_to_test:
            # 确保每个异常类都可以被实例化
            error = exception_class("测试消息")
            self.assertIsInstance(error, AutomationException)
            self.assertEqual(str(error), "测试消息")


if __name__ == "__main__":
    unittest.main()
