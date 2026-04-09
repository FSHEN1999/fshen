# -*- coding: utf-8 -*-
"""
UI助手模块 - 统一管理UI操作，优化等待逻辑，避免重复的waitUntil调用
"""

import logging
import time
from typing import Optional, List, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException
)

from config import config
from exceptions import (
    ElementNotFoundError,
    ElementTimeoutError,
    ElementClickError,
    ElementInputError
)


class SmartWait:
    """智能等待管理器 - 统一处理所有Selenium等待"""
    
    def __init__(self, driver: webdriver.Remote, timeout: int = None):
        self.driver = driver
        self.timeout = timeout or config.ui.wait_timeout
        self.wait = WebDriverWait(driver, self.timeout)
    
    def element_clickable(self, locator: Tuple[By, str], description: str = "") -> Optional[object]:
        """等待元素可点击"""
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            logging.debug(f"[Wait] 元素可点击: {description}")
            return element
        except TimeoutException:
            raise ElementTimeoutError(f"等待元素可点击超时 ({self.timeout}s): {description}")
    
    def element_visible(self, locator: Tuple[By, str], description: str = "") -> Optional[object]:
        """等待元素可见"""
        try:
            element = self.wait.until(EC.visibility_of_element_located(locator))
            logging.debug(f"[Wait] 元素可见: {description}")
            return element
        except TimeoutException:
            raise ElementTimeoutError(f"等待元素可见超时 ({self.timeout}s): {description}")
    
    def elements_present(self, locator: Tuple[By, str], description: str = "") -> List[object]:
        """等待多个元素出现"""
        try:
            elements = self.wait.until(EC.presence_of_all_elements_located(locator))
            logging.debug(f"[Wait] 找到 {len(elements)} 个元素: {description}")
            return elements
        except TimeoutException:
            raise ElementTimeoutError(f"等待多个元素出现超时 ({self.timeout}s): {description}")


class UIOperations:
    """UI操作集合 - 统一的UI操作方法"""
    
    @staticmethod
    def safe_click(driver: webdriver.Remote, locator: Tuple[By, str], description: str, 
                   fallback_locators: List[Tuple[By, str]] = None) -> bool:
        """
        安全点击元素，支持备选定位器和JavaScript点击
        
        Args:
            driver: WebDriver实例
            locator: 主定位器
            description: 操作描述
            fallback_locators: 备选定位器列表
        
        Returns:
            True如果点击成功，False否则
        
        Raises:
            ElementNotFoundError: 如果元素未找到
            ElementTimeoutError: 如果元素加载超时
            ElementClickError: 如果元素点击失败
        """
        smart_wait = SmartWait(driver)
        
        try:
            # 方法1：尝试主定位器
            try:
                element = smart_wait.element_clickable(locator, description)
                UIOperations._perform_click(driver, element, description)
                return True
            except ElementTimeoutError:
                if not fallback_locators:
                    raise
                logging.debug(f"[UI] 主定位器失败，尝试 {len(fallback_locators)} 个备选定位器")
            
            # 方法2：尝试备选定位器
            for i, fallback_locator in enumerate(fallback_locators or [], 1):
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(fallback_locator)
                    )
                    UIOperations._perform_click(driver, element, f"{description} (备选 #{i})")
                    return True
                except TimeoutException:
                    continue
            
            raise ElementNotFoundError(f"无法通过任何定位器找到元素: {description}")
        
        except (StaleElementReferenceException, ElementNotInteractableException) as e:
            raise ElementClickError(f"元素点击失败: {description}, 错误: {e}")
    
    @staticmethod
    def _perform_click(driver: webdriver.Remote, element: object, description: str):
        """执行点击操作"""
        try:
            # 滚动到元素位置
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.3)
            
            # 尝试常规点击
            try:
                element.click()
            except:
                # 如果常规点击失败，使用JavaScript点击
                logging.debug(f"[UI] 常规点击失败，使用JavaScript点击: {description}")
                driver.execute_script("arguments[0].click();", element)
            
            logging.info(f"[UI] 已点击: {description}")
        except Exception as e:
            raise ElementClickError(f"点击操作失败: {description}, 错误: {e}")
    
    @staticmethod
    def safe_send_keys(driver: webdriver.Remote, locator: Tuple[By, str], text: str, 
                       description: str, clear_first: bool = True) -> bool:
        """
        安全输入文本
        
        Args:
            driver: WebDriver实例
            locator: 元素定位器
            text: 要输入的文本
            description: 操作描述
            clear_first: 是否先清空输入框
        
        Returns:
            True如果输入成功
        
        Raises:
            ElementTimeoutError: 如果元素加载超时
            ElementInputError: 如果输入失败
        """
        smart_wait = SmartWait(driver)
        
        try:
            element = smart_wait.element_visible(locator, description)
            
            # 滚动到元素
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.3)
            
            # 清空输入框（如果需要）
            if clear_first:
                element.clear()
            
            # 输入文本
            element.send_keys(text)
            logging.info(f"[UI] 已输入文本 '{description}': {text[:30]}{'...' if len(text) > 30 else ''}")
            return True
        
        except ElementTimeoutError:
            raise
        except Exception as e:
            raise ElementInputError(f"输入文本失败 '{description}': {e}")
    
    @staticmethod
    def wait_for_element_condition(driver: webdriver.Remote, locator: Tuple[By, str],
                                   condition: str = "visible", timeout: int = None) -> bool:
        """
        等待元素满足特定条件
        
        Args:
            driver: WebDriver实例
            locator: 元素定位器
            condition: 条件类型 (visible, clickable, present)
            timeout: 超时时间
        
        Returns:
            True如果条件满足
        """
        wait = WebDriverWait(driver, timeout or config.ui.wait_timeout)
        
        try:
            if condition == "visible":
                wait.until(EC.visibility_of_element_located(locator))
            elif condition == "clickable":
                wait.until(EC.element_to_be_clickable(locator))
            elif condition == "present":
                wait.until(EC.presence_of_element_located(locator))
            else:
                raise ValueError(f"未知的条件: {condition}")
            
            return True
        except TimeoutException:
            return False
