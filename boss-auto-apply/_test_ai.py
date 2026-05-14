import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from ai_reply import call_hermes, ai_generate, should_use_ai
print("should_use_ai(greeting):", should_use_ai("greeting"))
r = call_hermes("用一句话说你是AI助手", timeout=30)
print("call_hermes result:", r)
r2 = ai_generate("greeting", [], {"title": "测试开发工程师", "company": "测试公司", "jd": "需要Python Selenium Requests MySQL经验", "salary": "20K", "tags": ["Python","Selenium"]})
print("ai_generate greeting:", r2)
