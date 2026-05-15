from __future__ import annotations

import html
import os
import zipfile
from pathlib import Path


OUT = Path.cwd() / "DPU_8条全流程测试用例.xlsx"


CASES = [
    [
        "TC-01",
        "FP-USD",
        "P1",
        "FP-USD 2K 标准全流程成功",
        "覆盖小额 USD 线下直接激活链路，验证授信、签约、放款、还款完整闭环。",
        "测试环境可用；用户手机号未注册或可重复造数；FUNDPARK USD 产品可选。",
        "Currency=USD; Amount=2,000; Funder=FUNDPARK",
        "1. 注册 USD 用户\n2. 选择 FUNDPARK USD 产品\n3. 发起审批并通过 2K 额度\n4. 完成 eSign\n5. 轮询 drawdown 到 SUBMITTED\n6. 发送 drawdown APPROVED\n7. 发起 repayment start\n8. 发送 repayment SUCCESS",
        "用户完成授信、签约、放款、还款；金额和币种均为 USD；各节点状态流转正确。",
        "dpu_application; dpu_credit_offer; dpu_drawdown; dpu_repayment; webhook response",
    ],
    [
        "TC-02",
        "FP-USD",
        "P0",
        "FP-USD 500K 主链路全流程成功",
        "覆盖标准高额 USD scenario_1 主路径，作为 FP-USD 冒烟主用例。",
        "REG/SIT 环境可用；SP/3PL 授权链路可用；webhook 可正常回调。",
        "Currency=USD; Amount=500,000; Funder=FUNDPARK; scenario=scenario_1",
        "1. 注册 USD 用户\n2. 完成 SP/3PL 授权\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 500K\n5. 发送 PSP start\n6. 发送 PSP completed\n7. 发送 eSign SUCCESS\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
        "application、credit offer、PSP、eSign、drawdown、repayment 状态全部成功；approved/signed/drawdown 金额一致。",
        "MeterSphere detail; dpu_application status; dpu_credit_offer signed_limit; PSP status; drawdown status; repayment status",
    ],
    [
        "TC-03",
        "FP-USD",
        "P1",
        "FP-USD 500K 放款拒绝全流程",
        "验证签约成功后 drawdown rejected 的业务处理，以及 repayment 不应继续触发。",
        "USD 用户已完成审批、PSP 和 eSign；drawdown webhook 支持 REJECTED 与 failureReason。",
        "Currency=USD; Amount=500,000; DrawdownStatus=REJECTED; failureReason=ER001/ER002/ER003/ER004/ER005",
        "1. 注册 USD 用户\n2. 完成 underwriting APPROVED\n3. 完成 approved offer\n4. 完成 PSP completed\n5. 完成 eSign SUCCESS\n6. 发送 drawdown REJECTED，并带 failureReason\n7. 尝试查询或触发 repayment",
        "签约成功但放款拒绝；drawdown 记录失败原因；无有效 repayment 或 repayment 不允许继续。",
        "dpu_drawdown failure_reason; loan status; repayment absence; user-facing status",
    ],
    [
        "TC-04",
        "FP-CNY",
        "P1",
        "FP-CNY 70K 标准全流程成功",
        "覆盖 CNY 小额直接激活链路，验证 CNY 固定利率和小额放款闭环。",
        "CNY 产品可选；FUNDPARK CNY 资方切换可用；测试手机号可注册。",
        "Currency=CNY; Amount=70,000; Funder=FUNDPARK",
        "1. 注册 CNY 用户\n2. 选择 FUNDPARK CNY 产品\n3. 审批通过 70K\n4. 完成 eSign\n5. 轮询 drawdown 到 SUBMITTED\n6. 发送 drawdown APPROVED\n7. 发起 repayment start\n8. 发送 repayment SUCCESS",
        "CNY 小额链路跑通；chargeBases 按 CNY 固定利率处理；放款和还款币种均为 CNY。",
        "prefer_finance_product_currency=CNY; chargeBases=Fixed; drawdown currency; repayment currency",
    ],
    [
        "TC-05",
        "FP-CNY",
        "P0",
        "FP-CNY 500K 主链路全流程成功",
        "覆盖 CNY 中额主链路，作为 FP-CNY 冒烟主用例。",
        "CNY 产品、FUNDPARK 切换、PSP、eSign、drawdown webhook 均可用。",
        "Currency=CNY; Amount=500,000; Funder=FUNDPARK",
        "1. 注册 CNY 用户\n2. 切换 FUNDPARK CNY\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 500K\n5. 发送 PSP start\n6. 发送 PSP completed\n7. 发送 eSign SUCCESS\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
        "全链路成功；所有额度、签约、放款、还款币种为 CNY；关键表状态一致。",
        "dpu_users currency; approved_limit_currency; signed_limit_currency; drawdown currency; repayment status",
    ],
    [
        "TC-06",
        "FP-CNY",
        "P1",
        "FP-CNY 1.5M 高额全流程成功",
        "覆盖 CNY 最高额度申请，验证高额 offer、审批、签约、放款状态一致性。",
        "CNY 1.5M offer 可选；环境额度策略允许高额审批通过。",
        "Currency=CNY; Amount=1,500,000; Funder=FUNDPARK",
        "1. 注册 CNY 用户\n2. 选择 1.5M offer\n3. 发送 underwriting APPROVED\n4. 发送 approved offer 1.5M\n5. 完成 PSP completed\n6. 完成 eSign SUCCESS\n7. 发送 drawdown APPROVED\n8. 发起 repayment start\n9. 发送 repayment SUCCESS",
        "高额 CNY 链路成功；approvedLimit、signedLimit、drawdownLimit 与 1.5M 一致。",
        "offer selection; approvedLimit=1,500,000 CNY; signedLimit=1,500,000 CNY; drawdownLimit",
    ],
    [
        "TC-07",
        "DMF",
        "P0",
        "DMF HSBC 线下注册到放款成功",
        "覆盖 HSBC/DMF 专用入口、页面元素和专用 PSP 分支的成功全链路。",
        "HSBC DMF 注册页可访问；HSBC 专用 UI locator 可用；HSBC PSP webhook 可用。",
        "Product=DMF; Channel=HSBC offline; PSP=HSBC dedicated branch",
        "1. 访问 DMF 注册页\n2. 完成 HSBC 线下注册\n3. 进入 HSBC 专用申请入口\n4. 完成审批\n5. 发送 HSBC PSP start\n6. 发送 HSBC PSP completed\n7. 完成 eSign\n8. 发送 drawdown APPROVED\n9. 发起 repayment start\n10. 发送 repayment SUCCESS",
        "HSBC DMF 页面、专用元素、PSP 分支均可用；全流程成功完成到还款。",
        "HSBC page locator; PSP start/completed; eSign status; drawdown status; repayment status",
    ],
    [
        "TC-08",
        "DMF",
        "P1",
        "DMF HSBC PSP 中断/失败全流程",
        "覆盖 DMF 专用 PSP 异常链路，验证 PSP 未完成时不能继续有效签约和放款。",
        "DMF 用户已完成注册和审批；可控制 HSBC PSP failed 或 pending。",
        "Product=DMF; PSPStatus=FAILED/PENDING",
        "1. 完成 DMF 注册\n2. 完成审批通过\n3. 触发 HSBC PSP start\n4. 模拟 PSP failed 或保持未 completed\n5. 尝试进入 eSign\n6. 尝试触发 drawdown\n7. 查询 application/PSP/drawdown 状态",
        "PSP 未完成时不能进入有效签约/放款；业务状态停留正确；页面或接口错误提示符合预期。",
        "PSP status; eSign blocked; drawdown not created or not approved; UI/error response",
    ],
]


ORDER = [
    ["1", "TC-02", "FP-USD 500K 主链路全流程成功", "双币种主链路冒烟"],
    ["2", "TC-05", "FP-CNY 500K 主链路全流程成功", "双币种主链路冒烟"],
    ["3", "TC-07", "DMF HSBC 线下注册到放款成功", "DMF 主链路冒烟"],
    ["4", "TC-01", "FP-USD 2K 标准全流程成功", "小额 USD 回归"],
    ["5", "TC-04", "FP-CNY 70K 标准全流程成功", "小额 CNY 回归"],
    ["6", "TC-06", "FP-CNY 1.5M 高额全流程成功", "高额 CNY 回归"],
    ["7", "TC-03", "FP-USD 500K 放款拒绝全流程", "异常链路"],
    ["8", "TC-08", "DMF HSBC PSP 中断/失败全流程", "异常链路"],
]


def col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def inline_cell(row: int, col: int, value: str, style: int = 0) -> str:
    ref = f"{col_name(col)}{row}"
    escaped = html.escape(str(value), quote=False)
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{escaped}</t></is></c>'


def row_xml(row_num: int, values: list[str], style: int = 0, height: int | None = None) -> str:
    attrs = f' r="{row_num}"'
    if height:
        attrs += f' ht="{height}" customHeight="1"'
    cells = "".join(inline_cell(row_num, i + 1, value, style) for i, value in enumerate(values))
    return f"<row{attrs}>{cells}</row>"


def sheet_xml(rows: list[tuple[int, list[str], int, int | None]], merges: list[str], cols: list[int]) -> str:
    cols_xml = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{width}" customWidth="1"/>'
        for i, width in enumerate(cols)
    )
    data = "".join(row_xml(row, values, style, height) for row, values, style, height in rows)
    merge_xml = ""
    if merges:
        merge_xml = f'<mergeCells count="{len(merges)}">' + "".join(f'<mergeCell ref="{m}"/>' for m in merges) + "</mergeCells>"
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<cols>{cols_xml}</cols>
<sheetData>{data}</sheetData>
{merge_xml}
<autoFilter ref="A4:J12"/>
<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>'''


def order_sheet_xml() -> str:
    rows = [
        (1, ["建议执行顺序", "", "", ""], 1, 28),
        (3, ["顺序", "编号", "Case名称", "说明"], 2, 24),
    ]
    rows += [(4 + i, item, 0, 30) for i, item in enumerate(ORDER)]
    xml = sheet_xml(rows, ["A1:D1"], [10, 12, 38, 24])
    return xml.replace('<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/>', '<pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/>').replace('<autoFilter ref="A4:J12"/>', '<autoFilter ref="A3:D11"/>')


def build() -> None:
    headers = ["编号", "类型", "优先级", "Case名称", "测试目标", "前置条件", "测试数据", "主流程步骤", "预期结果", "校验点"]
    rows = [
        (1, ["DPU 8条全流程测试用例"] + [""] * 9, 1, 28),
        (2, ["覆盖：FP-USD 3条、FP-CNY 3条、DMF 2条。全流程口径：注册/登录 -> 资方/授权 -> 核保 -> 审批 -> PSP -> eSign -> drawdown -> repayment。"] + [""] * 9, 1, 44),
        (4, headers, 2, 24),
    ]
    rows += [(5 + i, case, 0, 110) for i, case in enumerate(CASES)]
    case_xml = sheet_xml(rows, ["A1:J1", "A2:J2"], [10, 12, 10, 28, 38, 38, 34, 48, 42, 36])

    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Case明细" sheetId="1" r:id="rId1"/><sheet name="执行顺序" sheetId="2" r:id="rId2"/></sheets>
</workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        "xl/styles.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="3"><font><sz val="10"/><name val="Microsoft YaHei"/></font><font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/></font><font><b/><sz val="10"/><name val="Microsoft YaHei"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFD9EAF7"/></patternFill></fill></fills>
<borders count="2"><border/><border><left style="thin"><color rgb="FFD9D9D9"/></left><right style="thin"><color rgb="FFD9D9D9"/></right><top style="thin"><color rgb="FFD9D9D9"/></top><bottom style="thin"><color rgb="FFD9D9D9"/></bottom></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="1" borderId="1" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>''',
        "xl/worksheets/sheet1.xml": case_xml,
        "xl/worksheets/sheet2.xml": order_sheet_xml(),
        "docProps/core.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>DPU 8条全流程测试用例</dc:title><dc:creator>Codex</dc:creator></cp:coreProperties>''',
        "docProps/app.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Codex</Application></Properties>''',
    }

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content.encode("utf-8"))

    with zipfile.ZipFile(OUT, "r") as zf:
        required = {"xl/workbook.xml", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml", "xl/styles.xml"}
        missing = required.difference(zf.namelist())
        if missing:
            raise RuntimeError(f"missing xlsx parts: {missing}")
    print(os.fspath(OUT))


if __name__ == "__main__":
    build()
