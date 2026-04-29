# 数据库连接问题排查和修复报告

## 问题诊断

通过 DataGrip 可以成功连接数据库，但 Python 脚本无法连接。经过详细诊断，找到了三个关键问题：

### 问题 1：connect_timeout 参数单位错误
- **原值**：`connect_timeout: 1500`
- **问题**：PyMySQL 期望秒数，1500秒 = 25分钟太长，导致连接超时
- **修复**：改为 `connect_timeout: 15`（15秒）

### 问题 2：bind_address 强制绑定
- **原代码**：通过 `get_local_physical_ip()` 获取本地IP，然后绑定到 `bind_address`
- **问题**：PyMySQL 的 `bind_address` 参数用于指定本地出站网卡，不是连接地址。强制绑定反而会导致连接困难，因为 DataGrip 没有这样做
- **修复**：删除 `bind_address` 绑定和 `get_local_physical_ip()` 函数调用

### 问题 3：client_flag 参数
- **原代码**：`client_flag=CLIENT.INTERACTIVE`
- **问题**：此参数在某些情况下可能导致连接不稳定
- **修复**：删除此参数，仅使用 `autocommit=True`

## 修复范围

修复了以下三个文件：

1. **mock_sit.py**
   - 修复了所有环境的 connect_timeout 配置（sit, dev, uat, preprod, local）
   - 简化了 `connect()` 方法，删除 bind_address 和 client_flag 参数

2. **mock_uat.py**
   - 修复了所有环境的 connect_timeout 配置
   - 简化了 `connect()` 方法

3. **mockapi/mock_uat.py**
   - 修复了所有环境的 connect_timeout 配置
   - 简化了 `connect()` 方法

## 验证结果

✓ **所有诊断测试通过**：通过 `diagnose_db.py` 逐一验证了5种连接配置
- 基础连接 ✓
- 添加合理超时 ✓
- 添加 autocommit ✓
- 不使用 bind_address ✓
- 简化 client_flag ✓

✓ **修复验证**：运行 `test_db_fixed.py` 成功验证修复效果
- 数据库连接成功
- 测试查询正常
- 连接正确关闭

## 关键修改对比

### 修改前
```python
"connect_timeout": 1500,  # 错误：1500秒！
...
def connect(self) -> None:
    local_ip = get_local_physical_ip()  # 不必要
    connect_params['bind_address'] = local_ip  # 会导致问题
    self.conn = pymysql.connect(
        **connect_params,
        autocommit=True,
        client_flag=CLIENT.INTERACTIVE  # 不稳定
    )
```

### 修改后
```python
"connect_timeout": 15,  # 正确：15秒
...
def connect(self) -> None:
    connect_params = self.config.copy()
    self.conn = pymysql.connect(
        **connect_params,
        autocommit=True
    )
```

## 建议

由于 `get_local_physical_ip()` 函数已不再使用，建议在后续清理中考虑删除此函数以简化代码。

---

修复时间：2026-04-24
验证工具：diagnose_db.py, test_db_fixed.py
