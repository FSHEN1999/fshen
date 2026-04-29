# 单元测试完整指南

## 📚 概述

本指南说明如何为优化模块编写和运行单元测试，确保代码质量和功能正确性。

---

## 🎯 快速开始

### 1. **查看现有测试**

```
tests/
├── __init__.py
├── test_config.py          # Config模块测试
├── test_exceptions.py      # 异常类测试
├── test_webhook_service.py # Webhook服务测试
└── test_js_scripts.py      # JavaScript脚本测试
```

### 2. **运行所有测试**

**方式1：使用unittest（无需额外依赖）**
```bash
python run_tests.py
```

**方式2：使用pytest（需要安装pytest）**
```bash
pip install pytest pytest-html pytest-cov
python run_tests.py --pytest
```

### 3. **运行特定模块的测试**

```bash
python run_tests.py config        # 只测试config模块
python run_tests.py exceptions    # 只测试exceptions模块
python run_tests.py webhook_service  # 只测试webhook_service模块
python run_tests.py js_scripts    # 只测试js_scripts模块
```

### 4. **生成测试报告**

```bash
# 生成HTML报告
python run_tests.py --pytest --html

# 生成代码覆盖率报告
python run_tests.py --pytest --cov
```

---

## 📖 已有的单元测试

### **test_config.py** - 配置管理测试

| 测试类 | 测试方法 | 覆盖内容 |
|--------|---------|---------|
| `TestDatabaseConfig` | `test_database_config_creation` | 数据库配置对象创建 |
| | `test_database_config_defaults` | 默认值验证 |
| `TestUIConfig` | `test_ui_config_creation` | UI配置对象创建 |
| `TestFileConfig` | `test_file_config_creation` | 文件路径配置 |
| `TestPollingConfig` | `test_polling_config_creation` | 轮询配置 |
| `TestConfig` | `test_config_initialization` | Config初始化 |
| | `test_invalid_environment` | 无效环境检测 |
| | `test_missing_database_config` | 缺失配置检测 |
| | `test_config_to_dict` | 配置导出 |
| `TestLoadConfig` | `test_load_config_with_env` | 加载指定环境配置 |
| | `test_load_config_without_env_uses_default` | 默认环境加载 |

**运行该模块的测试：**
```bash
python run_tests.py config
python -m unittest tests.test_config -v
```

---

### **test_exceptions.py** - 异常类测试

| 测试类 | 测试方法 | 覆盖内容 |
|--------|---------|---------|
| `TestExceptionInheritance` | 6个测试方法 | 异常继承关系验证 |
| `TestExceptionMessages` | `test_exception_message` | 异常消息保留 |
| | `test_exception_message_with_from` | 异常链接 |
| `TestExceptionCatching` | `test_catch_specific_exception` | 特定异常捕获 |
| | `test_catch_parent_exception` | 父类异常捕获 |
| | `test_different_exceptions_separate_handling` | 不同异常分别处理 |
| `TestAllExceptionsExist` | `test_all_exception_classes` | 所有14个异常类验证 |

**运行该模块的测试：**
```bash
python run_tests.py exceptions
python -m unittest tests.test_exceptions -v
```

---

### **test_webhook_service.py** - Webhook服务测试

| 测试类 | 测试方法 | 覆盖内容 |
|--------|---------|---------|
| `TestEventType` | `test_all_event_types_exist` | 事件类型存在性 |
| | `test_event_type_values` | 事件类型值验证 |
| `TestWebhookServiceInitialization` | `test_webhook_service_creation` | 服务初始化 |
| | `test_webhook_service_with_different_timeout` | 自定义超时 |
| `TestSendUpdateOffer` | `test_send_update_offer_success` | 成功发送updateOffer |
| | `test_send_update_offer_failure` | updateOffer失败处理 |
| | `test_send_update_offer_timeout` | 请求超时处理 |
| | `test_send_update_offer_exception` | 异常处理 |
| `TestSendSystemEvents` | `test_send_system_events_success` | 成功发送系统事件 |
| | `test_send_system_events_failure` | 系统事件失败处理 |
| | `test_send_system_events_timeout` | 系统事件超时处理 |
| `TestWebhookRequestStructure` | `test_update_offer_request_body` | updateOffer请求体结构 |
| | `test_system_events_request_body` | 系统事件请求体结构 |

**运行该模块的测试：**
```bash
python run_tests.py webhook_service
python -m unittest tests.test_webhook_service -v
```

---

### **test_js_scripts.py** - JavaScript脚本测试

| 测试类 | 测试方法 | 覆盖内容 |
|--------|---------|---------|
| `TestJSScriptGeneration` | 5个测试方法 | 脚本生成功能 |
| `TestJSScriptParameterization` | 3个测试方法 | 参数处理（特殊字符、中文等） |
| `TestJSScriptComponents` | `test_script_returns_string` | 返回类型验证 |
| | `test_script_not_empty` | 脚本非空验证 |
| `TestJSScriptSyntax` | `test_script_contains_javascript_keywords` | JavaScript关键字检查 |
| | `test_set_value_script_contains_assignment` | 赋值操作检查 |

**运行该模块的测试：**
```bash
python run_tests.py js_scripts
python -m unittest tests.test_js_scripts -v
```

---

## 🚀 编写新的单元测试

### **步骤1：创建测试文件**

```bash
# 在tests目录下创建新测试文件
touch tests/test_new_module.py
```

### **步骤2：导入必要的库**

```python
import unittest
from unittest.mock import patch, MagicMock
from new_module import FunctionOrClass  # 导入要测试的模块
```

### **步骤3：创建测试类**

```python
class TestNewModule(unittest.TestCase):
    """新模块的测试类"""
    
    def setUp(self):
        """每个测试运行前执行"""
        self.test_data = {'key': 'value'}
    
    def tearDown(self):
        """每个测试运行后执行"""
        pass
    
    def test_function_success(self):
        """测试成功场景"""
        result = some_function(self.test_data)
        self.assertEqual(result, expected_value)
    
    def test_function_failure(self):
        """测试失败场景"""
        with self.assertRaises(ValueError):
            some_function(invalid_data)
```

### **步骤4：运行新测试**

```bash
python -m unittest tests.test_new_module -v
```

---

## 🎯 测试最佳实践

### **1. 使用Mock对象测试外部依赖**

```python
from unittest.mock import patch, MagicMock

@patch('module.requests.post')
def test_webhook_with_mock(self, mock_post):
    """使用mock测试HTTP请求"""
    # 配置mock返回值
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = '{"success": true}'
    
    # 调用被测函数
    result = send_webhook()
    
    # 验证mock被正确调用
    mock_post.assert_called_once()
    self.assertTrue(result)
```

### **2. 测试异常处理**

```python
def test_exception_handling(self):
    """测试异常处理"""
    with self.assertRaises(CustomException) as context:
        function_that_raises_exception()
    
    self.assertIn("错误信息", str(context.exception))
```

### **3. 参数化测试**

```python
import unittest
from parameterized import parameterized

class TestParameterized(unittest.TestCase):
    @parameterized.expand([
        ("input1", "expected1"),
        ("input2", "expected2"),
        ("input3", "expected3"),
    ])
    def test_with_parameters(self, input_val, expected):
        result = function(input_val)
        self.assertEqual(result, expected)
```

### **4. 测试覆盖率**

```bash
# 安装覆盖率工具
pip install coverage

# 运行并生成覆盖率报告
coverage run -m unittest discover -s tests -p "test_*.py"
coverage report
coverage html  # 生成HTML报告
```

---

## 📊 测试报告示例

运行 `python run_tests.py --pytest --html` 后，会生成以下报告：

```
test_reports/
├── test_report.html      # 测试执行报告（可在浏览器打开）
└── coverage/
    ├── index.html        # 覆盖率报告首页
    ├── status.json       # 覆盖率JSON数据
    └── ...
```

---

## 🔧 测试配置文件

### **pytest.ini** - Pytest配置

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers
```

---

## 📋 常见测试命令

| 命令 | 功能 |
|------|------|
| `python run_tests.py` | 快速运行所有测试 |
| `python run_tests.py config` | 只测试config模块 |
| `python run_tests.py --pytest` | 使用pytest运行 |
| `python run_tests.py --pytest --html` | 生成HTML报告 |
| `python run_tests.py --pytest --cov` | 生成覆盖率报告 |
| `python -m unittest discover -s tests -p "test_*.py" -v` | 手动运行所有测试 |
| `python -m unittest tests.test_config -v` | 手动运行单个测试模块 |

---

## 🐛 调试测试

### **查看详细日志**

```python
def test_with_logging(self):
    """带日志的测试"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    result = function_to_test()
    
    self.assertIsNotNone(result)
```

### **使用pdb调试**

```python
def test_with_breakpoint(self):
    """使用断点调试"""
    breakpoint()  # Python 3.7+
    result = function_to_test()
    self.assertEqual(result, expected)
```

或者：

```python
def test_with_pdb(self):
    """使用pdb调试"""
    import pdb; pdb.set_trace()
    result = function_to_test()
```

---

## 🎓 测试示例

### **示例1：测试配置加载**

```python
import unittest
from unittest.mock import patch
import os

class TestConfigLoading(unittest.TestCase):
    
    @patch.dict(os.environ, {
        "ENV": "uat",
        "DATABASE_HOST_UAT": "db.example.com",
        "DATABASE_USER_UAT": "user",
        "DATABASE_PASSWORD_UAT": "pass"
    })
    def test_load_uat_config(self):
        from config import load_config
        config = load_config(env="uat")
        
        self.assertEqual(config.environment, "uat")
        self.assertEqual(config.database.host, "db.example.com")
```

### **示例2：测试异常捕获**

```python
import unittest
from exceptions import ElementTimeoutError

class TestExceptionCatching(unittest.TestCase):
    
    def test_element_timeout_caught_correctly(self):
        try:
            raise ElementTimeoutError("元素未在30秒内加载")
        except ElementTimeoutError as e:
            self.assertIn("30秒", str(e))
        except Exception:
            self.fail("应该捕获ElementTimeoutError")
```

### **示例3：测试webhook服务**

```python
import unittest
from unittest.mock import patch, MagicMock
from webhook_service import WebhookService

class TestWebhookService(unittest.TestCase):
    
    @patch('webhook_service.requests.post')
    def test_webhook_success(self, mock_post):
        mock_post.return_value.status_code = 200
        
        service = WebhookService("https://api.example.com")
        success, response, error = service.send_update_offer(
            idempotency_key="key123",
            offer_id="offer456"
        )
        
        self.assertTrue(success)
        self.assertIsNone(error)
```

---

## 📚 参考资源

- [Python unittest官方文档](https://docs.python.org/3/library/unittest.html)
- [unittest.mock官方文档](https://docs.python.org/3/library/unittest.mock.html)
- [Pytest官方文档](https://docs.pytest.org/)
- [PEP 8 - Python代码风格指南](https://www.python.org/dev/peps/pep-0008/)

---

## ⚡ 快速参考

### **创建和运行第一个测试**

```bash
# 1. 创建测试文件
cat > tests/test_example.py << 'EOF'
import unittest

class TestExample(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(2 + 2, 4)

if __name__ == '__main__':
    unittest.main()
EOF

# 2. 运行测试
python -m unittest tests.test_example -v

# 3. 使用run_tests.py运行（如果存在）
python run_tests.py
```

---

## 🎯 下一步

1. ✅ 查看现有的单元测试文件，理解测试结构
2. ✅ 运行现有测试 `python run_tests.py`
3. ✅ 为自己的模块编写测试
4. ✅ 生成测试覆盖率报告 `python run_tests.py --pytest --cov`
5. ✅ 持续维护和更新测试用例

---

**最后更新**: 2025-04-07  
**使用pytest还是unittest?**: 如果没有特殊需求，用unittest就够了（内置库，无需安装）。需要高级功能（参数化、插件等）时，使用pytest。
