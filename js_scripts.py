# -*- coding: utf-8 -*-
"""
JavaScript脚本集合 - 存储所有用于Selenium自动化的JavaScript代码
"""

# 获取浏览器localStorage中的所有项
GET_LOCAL_STORAGE_JS = """
const items = {};
for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    const value = localStorage.getItem(key);
    items[key] = value;
}
return items;
"""

# 获取浏览器sessionStorage中的所有项
GET_SESSION_STORAGE_JS = """
const items = {};
for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    const value = sessionStorage.getItem(key);
    items[key] = value;
}
return items;
"""

# 查找文件输入框并设置文件路径
def get_file_input_upload_js(file_path: str) -> str:
    """动态生成文件上传JavaScript"""
    return f"""
    (function() {{
        var inputs = document.querySelectorAll('input[type="file"]');
        var targetInput = null;
        
        for (var i = 0; i < inputs.length; i++) {{
            if (inputs[i].offsetParent !== null && inputs[i].offsetParent !== document.body) {{
                targetInput = inputs[i];
                break;
            }}
        }}
        
        if (!targetInput && inputs.length > 0) {{
            targetInput = inputs[0];
        }}
        
        if (!targetInput) {{
            return {{success: false, message: '未找到file input'}};
        }}
        
        // 创建虚拟文件对象（模拟上传）
        var file = new File(["content"], "{file_path}", {{type: "image/png"}});
        var dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        targetInput.files = dataTransfer.files;
        
        // 触发change事件
        var event = new Event('change', {{bubbles: true}});
        targetInput.dispatchEvent(event);
        
        return {{success: true, inputCount: inputs.length}};
    }})();
    """

# 查询银行选项列表
GET_BANK_OPTIONS_JS = """
(function() {
    var items = document.querySelectorAll('li.el-select-dropdown__item, .el-select-dropdown__item');
    var results = [];
    for (var i = 0; i < items.length; i++) {
        var text = items[i].textContent.trim();
        if (text) {
            results.push({
                index: i,
                text: text
            });
        }
    }
    return {count: results.length, items: results};
})();
"""

# 选择银行选项
def get_select_bank_option_js(option_index: int = 2) -> str:
    """动态生成选择银行选项的JavaScript"""
    return f"""
    (function() {{
        var items = document.querySelectorAll('li.el-select-dropdown__item, .el-select-dropdown__item');
        if (items.length > {option_index}) {{
            items[{option_index}].click();
            return {{success: true, text: items[{option_index}].textContent.trim()}};
        }}
        return {{success: false}};
    }})();
    """

# 输入银行账号
def get_input_bank_account_js(bank_account: str) -> str:
    """动态生成输入银行账号的JavaScript"""
    return f"""
    (function() {{
        var inputs = document.querySelectorAll('input');
        for (var i = inputs.length - 1; i >= 0; i--) {{
            var input = inputs[i];
            if (input.offsetParent !== null &&
                input.type !== 'hidden' &&
                input.type !== 'submit' &&
                !input.readOnly &&
                !input.value) {{
                input.focus();
                input.value = '{bank_account}';
                var events = ['input', 'change', 'blur'];
                for (var j = 0; j < events.length; j++) {{
                    var event = new Event(events[j], {{bubbles: true}});
                    input.dispatchEvent(event);
                }}
                return {{success: true, tagName: input.tagName, type: input.type}};
            }}
        }}
        return {{success: false}};
    }})();
    """

# 通过更宽松的定位器查找并输入银行账号
def get_input_last_empty_input_js(bank_account: str) -> str:
    """动态生成使用最后一个空输入框的JavaScript"""
    return f"""
    (function() {{
        var inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([readonly])'));
        for (var i = inputs.length - 1; i >= 0; i--) {{
            if (inputs[i].offsetParent !== null && !inputs[i].value) {{
                inputs[i].focus();
                inputs[i].value = '{bank_account}';
                inputs[i].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[i].dispatchEvent(new Event('change', {{bubbles: true}}));
                return {{success: true}};
            }}
        }}
        return {{success: false}};
    }})();
    """

# 验证银行账号是否已输入
def get_verify_bank_account_js(bank_account: str) -> str:
    """动态生成验证银行账号输入的JavaScript"""
    bank_account_clean = bank_account.replace(' ', '').replace('-', '')
    return f"""
    (function() {{
        var inputs = document.querySelectorAll('input');
        var allValues = [];
        for (var i = 0; i < inputs.length; i++) {{
            var value = inputs[i].value;
            if (value) {{
                allValues.push(value);
                var cleanValue = value.replace(/\\s/g, '').replace(/-/g, '');
                if (cleanValue === '{bank_account_clean}') {{
                    return {{success: true, found: true, value: value, method: 'exact'}};
                }}
                if (cleanValue.includes('{bank_account_clean}') || '{bank_account_clean}'.includes(cleanValue)) {{
                    return {{success: true, found: true, partial: true, value: value, method: 'partial'}};
                }}
            }}
        }}
        var spans = document.querySelectorAll('.el-input__inner');
        for (var j = 0; j < spans.length; j++) {{
            if (spans[j].value) {{
                var cleanValue = spans[j].value.replace(/\\s/g, '').replace(/-/g, '');
                if (cleanValue === '{bank_account_clean}' || cleanValue.includes('{bank_account_clean}')) {{
                    return {{success: true, found: true, value: spans[j].value, method: 'el-input'}};
                }}
            }}
        }}
        return {{success: true, found: false, allValues: allValues}};
    }})();
    """


# ==================== 测试所需的简单函数 ====================

def get_element_value(selector: str) -> str:
    """获取元素的值"""
    return f"""
    (function() {{
        var element = document.querySelector('{selector}');
        if (element) {{
            return element.value || element.textContent;
        }}
        return null;
    }})();
    """


def set_element_value(selector: str, value: str) -> str:
    """设置元素的值"""
    return f"""
    (function() {{
        var element = document.querySelector('{selector}');
        if (element) {{
            element.value = '{value}';
            element.dispatchEvent(new Event('input', {{bubbles: true}}));
            element.dispatchEvent(new Event('change', {{bubbles: true}}));
            return true;
        }}
        return false;
    }})();
    """


def click_element(selector: str) -> str:
    """点击元素"""
    return f"""
    (function() {{
        var element = document.querySelector('{selector}');
        if (element) {{
            element.click();
            return true;
        }}
        return false;
    }})();
    """


def scroll_to_element(selector: str) -> str:
    """滚动到元素"""
    return f"""
    (function() {{
        var element = document.querySelector('{selector}');
        if (element) {{
            element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            return true;
        }}
        return false;
    }})();
    """


def remove_element(selector: str) -> str:
    """移除元素"""
    return f"""
    (function() {{
        var element = document.querySelector('{selector}');
        if (element) {{
            element.remove();
            return true;
        }}
        return false;
    }})();
    """
