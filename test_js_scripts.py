# -*- coding: utf-8 -*-
"""
测试 js_scripts.py JavaScript脚本生成模块
"""

import unittest
from libs import js_scripts


class TestJSScriptGeneration(unittest.TestCase):
    """JavaScript脚本生成测试"""
    
    def test_get_element_value_script(self):
        """测试获取元素值脚本"""
        script = js_scripts.get_element_value(".phone-input")
        
        self.assertIsInstance(script, str)
        self.assertIn(".phone-input", script)
        self.assertIn("return", script)
    
    def test_set_element_value_script(self):
        """测试设置元素值脚本"""
        script = js_scripts.set_element_value(".phone-input", "13800138000")
        
        self.assertIsInstance(script, str)
        self.assertIn(".phone-input", script)
        self.assertIn("13800138000", script)
    
    def test_click_element_script(self):
        """测试点击元素脚本"""
        script = js_scripts.click_element(".submit-btn")
        
        self.assertIsInstance(script, str)
        self.assertIn(".submit-btn", script)
        self.assertIn("click", script)
    
    def test_scroll_to_element_script(self):
        """测试滚动到元素脚本"""
        script = js_scripts.scroll_to_element(".target-element")
        
        self.assertIsInstance(script, str)
        self.assertIn(".target-element", script)
    
    def test_remove_element_script(self):
        """测试移除元素脚本"""
        script = js_scripts.remove_element(".popup-overlay")
        
        self.assertIsInstance(script, str)
        self.assertIn(".popup-overlay", script)


class TestJSScriptParameterization(unittest.TestCase):
    """JavaScript脚本参数化测试"""
    
    def test_script_with_special_characters(self):
        """测试包含特殊字符的参数"""
        value = "test@example.com"
        script = js_scripts.set_element_value(".email-input", value)
        
        self.assertIn(value, script)
    
    def test_script_with_chinese_characters(self):
        """测试包含中文字符的参数"""
        value = "测试用户名"
        script = js_scripts.set_element_value(".username-input", value)
        
        self.assertIn(value, script)
    
    def test_script_selector_variations(self):
        """测试不同选择器格式"""
        selectors = [
            ".class-selector",
            "#id-selector",
            "[data-test='value']",
            "input[type='text']"
        ]
        
        for selector in selectors:
            script = js_scripts.get_element_value(selector)
            self.assertIn(selector, script)


class TestJSScriptComponents(unittest.TestCase):
    """JavaScript脚本组件测试"""
    
    def test_script_returns_string(self):
        """测试所有脚本生成函数返回字符串"""
        methods = [
            (js_scripts.get_element_value, (".test",)),
            (js_scripts.set_element_value, (".test", "value")),
            (js_scripts.click_element, (".test",)),
            (js_scripts.scroll_to_element, (".test",)),
            (js_scripts.remove_element, (".test",)),
        ]
        
        for method, args in methods:
            result = method(*args)
            self.assertIsInstance(result, str, f"Method {method.__name__} should return string")
    
    def test_script_not_empty(self):
        """测试所有脚本都不为空"""
        methods = [
            (js_scripts.get_element_value, (".test",)),
            (js_scripts.set_element_value, (".test", "value")),
            (js_scripts.click_element, (".test",)),
            (js_scripts.scroll_to_element, (".test",)),
            (js_scripts.remove_element, (".test",)),
        ]
        
        for method, args in methods:
            result = method(*args)
            self.assertGreater(len(result), 0, f"Script from {method.__name__} should not be empty")


class TestJSScriptSyntax(unittest.TestCase):
    """JavaScript脚本语法验证"""
    
    def test_script_contains_javascript_keywords(self):
        """测试脚本包含JavaScript关键字"""
        script = js_scripts.get_element_value(".test")
        
        # 脚本应该包含某些JavaScript关键字
        self.assertTrue(
            "document" in script or "querySelector" in script or "function" in script,
            "Script should contain JavaScript keywords"
        )
    
    def test_set_value_script_contains_assignment(self):
        """测试设置值脚本包含赋值操作"""
        script = js_scripts.set_element_value(".input", "value")
        
        # 应该包含某种形式的赋值或设置操作
        self.assertTrue(
            "value" in script or "Value" in script or "textContent" in script,
            "Script should contain value assignment"
        )


if __name__ == "__main__":
    unittest.main()
