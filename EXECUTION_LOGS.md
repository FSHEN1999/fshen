# DPU Complete Flow Execution Logs

## 执行总结

### FP-USD
- **状态**: 部分完成（遇到REG环境限制）
- **Phone**: 18464251967
- **Merchant ID**: 93fcbae71c8b4ac1997c23a26fd434c9
- **问题**: REG环境不自动创建`dpu_manual_offer`，需手动插入
- **解决**: 手动插入记录后继续

### FP-CNY  
- **状态**: ✓ 已验证成功
- **Phone**: 18221109584
- **Merchant ID**: 57a61838cb7a49318f085ea0653e4fb5
- **E-sign Status**: SUCCESS
- **Amount**: 1600000.00 CNY

## 详细日志请查看
- `complete_usd_20260428_214724.log` - USD初始执行
- `run_esign_simple_20260428_204353.log` - USD简化webhook成功
- 数据库验证查询结果

## 关键发现
1. REG环境SP授权后需手动创建manual_offer
2. Webhook格式必须严格匹配
3. CNY和USD流程相同，仅currency字段不同
4. 完整流程约2-3分钟
