# 单元测试快速参考

## 🚀 1分钟快速开始

### 运行所有测试
```bash
python run_tests.py
```

### 运行特定模块测试
```bash
python run_tests.py config          # config模块
python run_tests.py exceptions      # exceptions模块
python run_tests.py webhook_service # webhook_service模块
python run_tests.py js_scripts      # js_scripts模块
```

### 生成测试报告
```bash
python run_tests.py --pytest --html    # HTML报告
python run_tests.py --pytest --cov     # 覆盖率报告
```

---

## 📊 测试统计

| 模块 | 测试类数 | 测试方法数 | 状态 |
|------|---------|-----------|------|
| **config.py** | 5 | 11 | ✅ |
| **exceptions.py** | 5 | 11 | ✅ |
| **webhook_service.py** | 5 | 13 | ✅ |
| **js_scripts.py** | 4 | 13 | ✅ |
| **合计** | **19** | **48** | **✅ 全通过** |

---

## 📝 已有的测试覆盖

### **config.py** - 11个测试

```python
# DatabaseConfig相关
✅ test_database_config_creation          # 数据库配置创建
✅ test_database_config_defaults          # 默认值

# UIConfig相关
✅ test_ui_config_creation                # UI配置创建

# FileConfig相关
✅ test_file_config_creation              # 文件配置创建

# PollingConfig相关
✅ test_polling_config_creation           # 轮询配置创建

# Config类相关
✅ test_config_initialization             # 初始化
✅ test_invalid_environment               # 无效环境检测
✅ test_missing_database_config           # 缺失配置检测
✅ test_config_to_dict                    # 导出字典

# load_config函数
✅ test_load_config_with_env              # 加载指定环境
✅ test_load_config_without_env_uses_default # 使用默认环境
```

### **exceptions.py** - 11个测试

```python
# 异常继承关系（6个测试）
✅ test_element_timeout_error_inheritance     
✅ test_database_exception_inheritance        
✅ test_api_exception_inheritance             
✅ test_file_exception_inheritance            
✅ test_browser_exception_inheritance         
✅ test_validation_exception_inheritance      

# 异常消息（2个测试）
✅ test_exception_message                     # 消息保留
✅ test_exception_message_with_from          # 异常链接

# 异常捕获（3个测试）
✅ test_catch_specific_exception              # 特定异常
✅ test_catch_parent_exception                # 父类异常
✅ test_different_exceptions_separate_handling # 分别处理

# 异常类验证（1个测试）
✅ test_all_exception_classes                 # 14个异常类都存在
```

### **webhook_service.py** - 13个测试

```python
# EventType枚举（2个测试）
✅ test_all_event_types_exist                # 所有事件类型存在
✅ test_event_type_values                    # 事件类型值检查

# 初始化（2个测试）
✅ test_webhook_service_creation             # 创建服务
✅ test_webhook_service_with_different_timeout # 自定义超时

# send_update_offer（4个测试）
✅ test_send_update_offer_success            # 成功发送
✅ test_send_update_offer_failure            # 失败处理
✅ test_send_update_offer_timeout            # 超时处理
✅ test_send_update_offer_exception          # 异常处理

# send_system_events（3个测试）
✅ test_send_system_events_success           # 成功发送
✅ test_send_system_events_failure           # 失败处理
✅ test_send_system_events_timeout           # 超时处理

# 请求体结构（2个测试）
✅ test_update_offer_request_body            # updateOffer请求体
✅ test_system_events_request_body           # 系统事件请求体
```

### **js_scripts.py** - 13个测试

```python
# 脚本生成（5个测试）
✅ test_get_element_value_script             # 获取值脚本
✅ test_set_element_value_script             # 设置值脚本
✅ test_click_element_script                 # 点击脚本
✅ test_scroll_to_element_script             # 滚动脚本
✅ test_remove_element_script                # 移除脚本

# 参数化（3个测试）
✅ test_script_with_special_characters       # 特殊字符处理
✅ test_script_with_chinese_characters       # 中文处理
✅ test_script_selector_variations           # 选择器变种

# 组件验证（2个测试）
✅ test_script_returns_string                # 返回字符串
✅ test_script_not_empty                     # 不为空

# 语法验证（2个测试）
✅ test_script_contains_javascript_keywords  # JavaScript关键字
✅ test_set_value_script_contains_assignment # 赋值操作
```

---

## 🎯 为新模块编写测试

### 模板1：数据验证测试
```python
import unittest
from my_module import MyClass

class TestMyModule(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.obj = MyClass()
    
    def test_creation(self):
        """测试对象创建"""
        self.assertIsNotNone(self.obj)
    
    def test_property(self):
        """测试属性"""
        self.assertEqual(self.obj.property_name, expected_value)
```

### 模板2：异常测试
```python
def test_exception_handling(self):
    """测试异常处理"""
    with self.assertRaises(CustomException) as context:
        function_that_raises()
    
    self.assertIn("错误信息", str(context.exception))
```

### 模板3：Mock测试（外部依赖）
```python
from unittest.mock import patch, MagicMock

@patch('module.external_function')
def test_with_mock(self, mock_func):
    """使用mock测试外部依赖"""
    mock_func.return_value = "mocked value"
    
    result = function_using_external()
    
    self.assertEqual(result, expected)
    mock_func.assert_called_once()
```

---

## 🔧 常见操作

### 查看某个测试类的具体测试
```bash
python -m unittest tests.test_config.TestConfig -v
```

### 查看某个具体的测试方法
```bash
python -m unittest tests.test_config.TestConfig.test_config_initialization -v
```

### 运行tests目录下所有测试（不用run_tests.py）
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### 使用pytest（需要先安装）
```bash
pip install pytest pytest-html pytest-cov

# 运行所有测试
pytest tests/ -v

# 生成HTML报告
pytest tests/ -v --html=test_report.html --self-contained-html

# 生成覆盖率报告
pytest tests/ -v --cov=. --cov-report=html:coverage
```

---

## 📚 测试文件位置

```
tests/
├── __init__.py                 # 包初始化文件
├── test_config.py              # config模块测试（11个）
├── test_exceptions.py          # exceptions模块测试（11个）
├── test_webhook_service.py     # webhook_service模块测试（13个）
└── test_js_scripts.py          # js_scripts模块测试（13个）

run_tests.py                     # 测试运行脚本
pytest.ini                       # pytest配置文件
UNIT_TEST_GUIDE.md              # 详细测试指南

test_reports/                    # 测试报告目录（生成后）
├── test_report.html             # HTML测试报告
└── coverage/                     # 覆盖率报告
    ├── index.html
    └── ...
```

---

## ✅ 验证测试成功

运行以下命令确认所有测试通过：

```bash
$ python run_tests.py

2026-04-07 17:07:19 - INFO - 开始验证模块导入...
2026-04-07 17:07:19 - INFO - Ran 48 tests in 0.025s
2026-04-07 17:07:19 - INFO - 
2026-04-07 17:07:19 - INFO - ✅ 所有测试通过！
```

---

## 🎓 学习资源

| 资源 | 说明 |
|------|------|
| [UNIT_TEST_GUIDE.md](UNIT_TEST_GUIDE.md) | 详细的单元测试完整指南 |
| [tests/test_config.py](tests/test_config.py) | Config模块测试示例 |
| [tests/test_exceptions.py](tests/test_exceptions.py) | 异常处理测试示例 |
| [tests/test_webhook_service.py](tests/test_webhook_service.py) | Mock测试示例 |
| [tests/test_js_scripts.py](tests/test_js_scripts.py) | 函数返回值测试示例 |

---

## 📈 下一步

1. ✅ 查看现有的48个测试
2. ✅ 运行 `python run_tests.py` 确认测试通过
3. ✅ 为自己的新模块参考这些测试用例编写测试
4. ✅ 生成覆盖率报告 `python run_tests.py --pytest --cov`
5. ✅ 在CI/CD流水线中集成这些测试

---

**最后更新**: 2025-04-07  
**测试框架**: unittest（Python标准库）+ pytest（可选）  
**总测试数**: 48个  
**通过率**: 100% ✅
