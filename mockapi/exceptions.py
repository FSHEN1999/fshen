# -*- coding: utf-8 -*-
"""
自定义异常类 - 用于细粒度的异常处理
"""


class AutomationException(Exception):
    """自动化基础异常"""
    pass


class UIElementException(AutomationException):
    """UI元素相关异常"""
    pass


class ElementNotFoundError(UIElementException):
    """元素未找到异常"""
    pass


class ElementTimeoutError(UIElementException):
    """元素加载超时异常"""
    pass


class ElementClickError(UIElementException):
    """元素点击异常"""
    pass


class ElementInputError(UIElementException):
    """元素输入异常"""
    pass


class DatabaseException(AutomationException):
    """数据库相关异常"""
    pass


class DatabaseConnectionError(DatabaseException):
    """数据库连接异常"""
    pass


class DatabaseQueryError(DatabaseException):
    """数据库查询异常"""
    pass


class DatabaseTimeoutError(DatabaseException):
    """数据库操作超时异常"""
    pass


class APIException(AutomationException):
    """API相关异常"""
    pass


class APIRequestError(APIException):
    """API请求异常"""
    pass


class APITimeoutError(APIException):
    """API请求超时异常"""
    pass


class APIResponseError(APIException):
    """API响应异常"""
    pass


class FileException(AutomationException):
    """文件相关异常"""
    pass


class FileNotFoundError(FileException):
    """文件未找到异常"""
    pass


class FileReadError(FileException):
    """文件读取异常"""
    pass


class FileWriteError(FileException):
    """文件写入异常"""
    pass


class FileUploadError(FileException):
    """文件上传异常"""
    pass


class BrowserException(AutomationException):
    """浏览器相关异常"""
    pass


class BrowserInitError(BrowserException):
    """浏览器初始化异常"""
    pass


class BrowserProcessError(BrowserException):
    """浏览器进程异常"""
    pass


class BrowserConnectionError(BrowserException):
    """浏览器连接异常"""
    pass


class ValidationException(AutomationException):
    """数据验证相关异常"""
    pass


class ValidationError(ValidationException):
    """验证失败异常"""
    pass


class DataValidationError(ValidationException):
    """数据验证失败异常"""
    pass


class BrowserNavigationError(BrowserException):
    """浏览器导航异常"""
    pass


class ValidationException(AutomationException):
    """验证异常"""
    pass


class DataValidationError(ValidationException):
    """数据验证异常"""
    pass


class ConfigError(AutomationException):
    """配置异常"""
    pass
