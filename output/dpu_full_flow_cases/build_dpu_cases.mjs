import { Workbook } from "@oai/artifact-tool";
import path from "node:path";

const outDir = process.cwd();
const outPath = path.join(outDir, "DPU_8条全流程测试用例.xlsx");

const cases = [
  {
    id: "TC-01",
    product: "FP-USD",
    priority: "P1",
    title: "FP-USD 2K 标准全流程成功",
    objective: "覆盖小额 USD 线下直接激活链路，验证授信、签约、放款、还款完整闭环。",
    precondition: "测试环境可用；用户手机号未注册或可重复造数；FUNDPARK USD 产品可选。",
    data: "Currency=USD; Amount=2,000; Funder=FUNDPARK",
    steps: "1. 注册 USD 用户\n2. 选择 FUNDPARK USD 产品\n3. 发起审批并通过 2K 额度\n4. 完成 eSign\n5. 轮询 drawdown 到 SUBMITTED\n6. 发送 drawdown APPROVED\n7. 发起 repayment start\n8. 发送 repayment SUCCESS",
    expected: "用户完成授信、签约、放款、还款；金额和币种均为 USD；各节点状态流转正确。",
    checkpoints: "dpu_application; dpu_credit_offer; dpu_drawdown; dpu_repayment; webhook response",
  },
  {
    id: "TC-02",
    product: "FP-USD",
    priority: "P0",
    title: "FP-USD 500K 主链路全流程成功",
    objective: "覆盖标准高额 USD scenario_1 主路径，作为 FP-USD 冒烟主用例。",
    precondition: "REG/SIT 环境可用；SP/3PL 授权链路可用；webhook 可正常回调。",
    data: "Currency=USD; Amount=500,000; Funder=FUNDPARK; scenario=scenario_1",
    steps: "1. 注册 USD 用户\n2. 完成 SP/3PL 授权\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 500K\n5. 发送 PSP start\n6. 发送 PSP completed\n7. 发送 eSign SUCCESS\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
    expected: "application、credit offer、PSP、eSign、drawdown、repayment 状态全部成功；approved/signed/drawdown 金额一致。",
    checkpoints: "MeterSphere detail; dpu_application status; dpu_credit_offer signed_limit; PSP status; drawdown status; repayment status",
  },
  {
    id: "TC-03",
    product: "FP-USD",
    priority: "P1",
    title: "FP-USD 500K 放款拒绝全流程",
    objective: "验证签约成功后 drawdown rejected 的业务处理，以及 repayment 不应继续触发。",
    precondition: "USD 用户已完成审批、PSP 和 eSign；drawdown webhook 支持 REJECTED 与 failureReason。",
    data: "Currency=USD; Amount=500,000; DrawdownStatus=REJECTED; failureReason=ER001/ER002/ER003/ER004/ER005",
    steps: "1. 注册 USD 用户\n2. 完成 underwriting APPROVED\n3. 完成 approved offer\n4. 完成 PSP completed\n5. 完成 eSign SUCCESS\n6. 发送 drawdown REJECTED，并带 failureReason\n7. 尝试查询或触发 repayment",
    expected: "签约成功但放款拒绝；drawdown 记录失败原因；无有效 repayment 或 repayment 不允许继续。",
    checkpoints: "dpu_drawdown failure_reason; loan status; repayment absence; user-facing status",
  },
  {
    id: "TC-04",
    product: "FP-CNY",
    priority: "P1",
    title: "FP-CNY 70K 标准全流程成功",
    objective: "覆盖 CNY 小额直接激活链路，验证 CNY 固定利率和小额放款闭环。",
    precondition: "CNY 产品可选；FUNDPARK CNY 资方切换可用；测试手机号可注册。",
    data: "Currency=CNY; Amount=70,000; Funder=FUNDPARK",
    steps: "1. 注册 CNY 用户\n2. 选择 FUNDPARK CNY 产品\n3. 审批通过 70K\n4. 完成 eSign\n5. 轮询 drawdown 到 SUBMITTED\n6. 发送 drawdown APPROVED\n7. 发起 repayment start\n8. 发送 repayment SUCCESS",
    expected: "CNY 小额链路跑通；chargeBases 按 CNY 固定利率处理；放款和还款币种均为 CNY。",
    checkpoints: "prefer_finance_product_currency=CNY; chargeBases=Fixed; drawdown currency; repayment currency",
  },
  {
    id: "TC-05",
    product: "FP-CNY",
    priority: "P0",
    title: "FP-CNY 500K 主链路全流程成功",
    objective: "覆盖 CNY 中额主链路，作为 FP-CNY 冒烟主用例。",
    precondition: "CNY 产品、FUNDPARK 切换、PSP、eSign、drawdown webhook 均可用。",
    data: "Currency=CNY; Amount=500,000; Funder=FUNDPARK",
    steps: "1. 注册 CNY 用户\n2. 切换 FUNDPARK CNY\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 500K\n5. 发送 PSP start\n6. 发送 PSP completed\n7. 发送 eSign SUCCESS\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
    expected: "全链路成功；所有额度、签约、放款、还款币种为 CNY；关键表状态一致。",
    checkpoints: "dpu_users currency; approved_limit_currency; signed_limit_currency; drawdown currency; repayment status",
  },
  {
    id: "TC-06",
    product: "FP-CNY",
    priority: "P1",
    title: "FP-CNY 1.5M 高额全流程成功",
    objective: "覆盖 CNY 最高额度申请，验证高额 offer、审批、签约、放款状态一致性。",
    precondition: "CNY 1.5M offer 可选；环境额度策略允许高额审批通过。",
    data: "Currency=CNY; Amount=1,500,000; Funder=FUNDPARK",
    steps: "1. 注册 CNY 用户\n2. 选择 1.5M offer\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 1.5M\n5. 完成 PSP completed\n6. 完成 eSign SUCCESS\n7. 发送 drawdown APPROVED\n8. 发起 repayment start\n9. 发送 repayment SUCCESS",
    expected: "高额 CNY 链路成功；approvedLimit、signedLimit、drawdownLimit 与 1.5M 一致。",
    checkpoints: "offer selection; approvedLimit=1,500,000 CNY; signedLimit=1,500,000 CNY; drawdownLimit",
  },
  {
    id: "TC-07",
    product: "DMF",
    priority: "P0",
    title: "DMF HSBC 线下注册到放款成功",
    objective: "覆盖 HSBC/DMF 专用入口、页面元素和专用 PSP 分支的成功全链路。",
    precondition: "HSBC DMF 注册页可访问；HSBC 专用 UI locator 可用；HSBC PSP webhook 可用。",
    data: "Product=DMF; Channel=HSBC offline; PSP=HSBC dedicated branch",
    steps: "1. 访问 DMF 注册页\n2. 完成 HSBC 线下注册\n3. 进入 HSBC 专用申请入口\n4. 完成审批\n5. 发送 HSBC PSP start\n6. 发送 HSBC PSP completed\n7. 完成 eSign\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
    expected: "HSBC DMF 页面、专用元素、PSP 分支均可用；全流程成功完成到还款。",
    checkpoints: "HSBC page locator; PSP start/completed; eSign status; drawdown status; repayment status",
  },
  {
    id: "TC-08",
    product: "DMF",
    priority: "P1",
    title: "DMF HSBC PSP 中断/失败全流程",
    objective: "覆盖 DMF 专用 PSP 异常链路，验证 PSP 未完成时不能继续有效签约和放款。",
    precondition: "DMF 用户已完成注册和审批；可控制 HSBC PSP failed 或 pending。",
    data: "Product=DMF; PSPStatus=FAILED/PENDING",
    steps: "1. 完成 DMF 注册\n2. 完成审批通过\n3. 触发 HSBC PSP start\n4. 模拟 PSP failed 或保持未 completed\n5. 尝试进入 eSign\n6. 尝试触发 drawdown\n7. 查询 application/PSP/drawdown 状态",
    expected: "PSP 未完成时不能进入有效签约/放款；业务状态停留正确；页面或接口错误提示符合预期。",
    checkpoints: "PSP status; eSign blocked; drawdown not created or not approved; UI/error response",
  },
];

const executionOrder = [
  ["1", "TC-02", "FP-USD 500K 主链路全流程成功", "双币种主链路冒烟"],
  ["2", "TC-05", "FP-CNY 500K 主链路全流程成功", "双币种主链路冒烟"],
  ["3", "TC-07", "DMF HSBC 线下注册到放款成功", "DMF 主链路冒烟"],
  ["4", "TC-01", "FP-USD 2K 标准全流程成功", "小额 USD 回归"],
  ["5", "TC-04", "FP-CNY 70K 标准全流程成功", "小额 CNY 回归"],
  ["6", "TC-06", "FP-CNY 1.5M 高额全流程成功", "高额 CNY 回归"],
  ["7", "TC-03", "FP-USD 500K 放款拒绝全流程", "异常链路"],
  ["8", "TC-08", "DMF HSBC PSP 中断/失败全流程", "异常链路"],
];

const workbook = new Workbook({ title: "DPU 8条全流程测试用例" });
const caseSheet = workbook.addWorksheet("Case明细");
const orderSheet = workbook.addWorksheet("执行顺序");

caseSheet.getCell("A1").value = "DPU 8条全流程测试用例";
caseSheet.getCell("A2").value = "覆盖：FP-USD 3条、FP-CNY 3条、DMF 2条。全流程口径：注册/登录 -> 资方/授权 -> 核保 -> 审批 -> PSP -> eSign -> drawdown -> repayment。";

const headers = ["编号", "类型", "优先级", "Case名称", "测试目标", "前置条件", "测试数据", "主流程步骤", "预期结果", "校验点"];
caseSheet.getRow(4).values = headers;
cases.forEach((item, index) => {
  const row = caseSheet.getRow(5 + index);
  row.values = [
    item.id,
    item.product,
    item.priority,
    item.title,
    item.objective,
    item.precondition,
    item.data,
    item.steps,
    item.expected,
    item.checkpoints,
  ];
});

orderSheet.getCell("A1").value = "建议执行顺序";
orderSheet.getRow(3).values = ["顺序", "编号", "Case名称", "说明"];
executionOrder.forEach((row, index) => {
  orderSheet.getRow(4 + index).values = row;
});

for (const sheet of [caseSheet, orderSheet]) {
  sheet.views = [{ state: "frozen", ySplit: sheet.name === "Case明细" ? 4 : 3 }];
  sheet.getUsedRange().style = {
    font: { name: "Microsoft YaHei", size: 10 },
    alignment: { vertical: "top", wrapText: true },
  };
}

caseSheet.getRange("A1:J1").merge();
caseSheet.getRange("A2:J2").merge();
caseSheet.getRange("A1:J2").style = {
  fill: { color: "1F4E78" },
  font: { color: "FFFFFF", bold: true, name: "Microsoft YaHei" },
  alignment: { wrapText: true, vertical: "middle" },
};
caseSheet.getRange("A4:J4").style = {
  fill: { color: "D9EAF7" },
  font: { bold: true, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle", wrapText: true },
};
caseSheet.getRange("A4:J12").addTable({ name: "DPUFullFlowCases", hasHeaders: true });

caseSheet.getColumn("A").width = 10;
caseSheet.getColumn("B").width = 12;
caseSheet.getColumn("C").width = 10;
caseSheet.getColumn("D").width = 28;
caseSheet.getColumn("E").width = 38;
caseSheet.getColumn("F").width = 38;
caseSheet.getColumn("G").width = 34;
caseSheet.getColumn("H").width = 48;
caseSheet.getColumn("I").width = 42;
caseSheet.getColumn("J").width = 36;
for (let r = 5; r <= 12; r++) caseSheet.getRow(r).height = 110;
caseSheet.getRow(1).height = 28;
caseSheet.getRow(2).height = 44;

orderSheet.getRange("A1:D1").merge();
orderSheet.getRange("A1:D1").style = {
  fill: { color: "1F4E78" },
  font: { color: "FFFFFF", bold: true, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle" },
};
orderSheet.getRange("A3:D3").style = {
  fill: { color: "D9EAF7" },
  font: { bold: true, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle" },
};
orderSheet.getRange("A3:D11").addTable({ name: "DPUExecutionOrder", hasHeaders: true });
orderSheet.getColumn("A").width = 10;
orderSheet.getColumn("B").width = 12;
orderSheet.getColumn("C").width = 38;
orderSheet.getColumn("D").width = 24;

await workbook.xlsx.writeFile(outPath);
console.log(outPath);
