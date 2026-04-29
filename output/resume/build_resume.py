from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(r"D:\data\project\dpu\output\resume")
PNG_PATH = BASE_DIR / "蔡欣妮_新媒体内容运营_品牌推广简历.png"
PDF_PATH = BASE_DIR / "蔡欣妮_新媒体内容运营_品牌推广简历.pdf"
FONT_PATH = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")

PAGE_WIDTH = 2480
PAGE_HEIGHT = 3508
MARGIN_X = 170
MARGIN_TOP = 150
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2

BG = "#F8F7F4"
TEXT = "#1F1F1F"
MUTED = "#666666"
ACCENT = "#2F5D50"
LIGHT = "#A9B1AD"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=size)


F_NAME = load_font(70)
F_ROLE = load_font(38)
F_CONTACT = load_font(26)
F_SECTION = load_font(34)
F_BODY = load_font(28)
F_COMPANY = load_font(31)
F_META = load_font(27)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def line_height(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, extra: int = 0) -> int:
    _, top, _, bottom = draw.textbbox((0, 0), "测试Ag", font=font)
    return bottom - top + extra


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    if not text:
        return [""]

    paragraphs = text.split("\n")
    lines: list[str] = []

    for para in paragraphs:
        if not para:
            lines.append("")
            continue

        current = ""
        for char in para:
            candidate = current + char
            if text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)

    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    spacing: int,
) -> int:
    x, y = xy
    height = line_height(draw, font, spacing)
    lines = wrap_text(draw, text, font, max_width)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += height
    return y


def draw_bullet_list(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    start_y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    indent: int = 38,
    gap_after: int = 10,
) -> int:
    y = start_y
    bullet_gap = 18
    for item in items:
        draw.text((MARGIN_X + 2, y), "•", font=font, fill=ACCENT)
        y = draw_wrapped_text(
            draw,
            item,
            (MARGIN_X + indent, y),
            font,
            fill,
            CONTENT_WIDTH - indent,
            spacing=8,
        )
        y += gap_after
    return y


def draw_job(
    draw: ImageDraw.ImageDraw,
    company: str,
    title: str,
    period: str,
    bullets: list[str],
    start_y: int,
) -> int:
    draw.text((MARGIN_X, start_y), company, font=F_COMPANY, fill=TEXT)
    company_width = text_width(draw, company, F_COMPANY)
    meta_x = MARGIN_X + company_width + 18
    draw.text((meta_x, start_y + 3), f"| {title} | {period}", font=F_META, fill=MUTED)
    y = start_y + line_height(draw, F_COMPANY, 4) + 8
    y = draw_bullet_list(draw, bullets, y, F_BODY, TEXT, indent=38, gap_after=8)
    return y + 18


def draw_section(draw: ImageDraw.ImageDraw, title: str, y: int) -> int:
    draw.text((MARGIN_X, y), title, font=F_SECTION, fill=ACCENT)
    y += line_height(draw, F_SECTION, 0) + 6
    draw.line((MARGIN_X, y, PAGE_WIDTH - MARGIN_X, y), fill=ACCENT, width=3)
    return y + 22


def build_resume() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    y = MARGIN_TOP
    draw.text((MARGIN_X, y), "蔡欣妮", font=F_NAME, fill=ACCENT)
    y += line_height(draw, F_NAME, 8)

    draw.text((MARGIN_X, y), "新媒体内容运营 / 品牌推广", font=F_ROLE, fill=TEXT)
    y += line_height(draw, F_ROLE, 8)

    draw.text(
        (MARGIN_X, y),
        "出生年月：2001.05  |  手机：13510575353  |  邮箱：623398404@qq.com",
        font=F_CONTACT,
        fill=MUTED,
    )
    y += line_height(draw, F_CONTACT, 12)
    draw.line((MARGIN_X, y, PAGE_WIDTH - MARGIN_X, y), fill=LIGHT, width=2)
    y += 34

    y = draw_section(draw, "个人简介", y)
    y = draw_wrapped_text(
        draw,
        "英国诺丁汉特伦特大学奢侈品时尚品牌管理硕士，兼具家具与产品设计本科背景，具备品牌审美、内容策划与执行落地能力。曾在轻奢女装、专业运动品牌与独立设计师品牌中独立完成达人种草、内容审核、预算分配与数据复盘，可围绕品牌调性和转化目标搭建可执行的社媒推广方案。",
        (MARGIN_X, y),
        F_BODY,
        TEXT,
        CONTENT_WIDTH,
        spacing=10,
    )
    y += 18

    y = draw_section(draw, "核心优势", y)
    y = draw_bullet_list(
        draw,
        [
            "沉淀 300+ 达人资源，覆盖小红书、抖音、得物等平台，能快速完成筛选、建联与长期维护。",
            "擅长从品牌定位出发输出 Brief、脚本和笔记方向，让内容兼顾调性、卖点和传播力。",
            "熟悉预算拆分、投流加热、效果监测和复盘优化，能够在控制 CPM 的同时提升曝光和搜索。",
            "具备供应商、商品、仓库和达人多方协同经验，可保障样品流转、排期和发布节点高效推进。",
            "已累计沉淀 700+ 条可复用传播素材，便于后续二次传播和终端转化。",
        ],
        y,
        F_BODY,
        TEXT,
    )
    y += 6

    y = draw_section(draw, "工作经历", y)
    y = draw_job(
        draw,
        "深圳市川崎运动用品有限公司",
        "新媒体内容运营专员",
        "2025.10 - 至今",
        [
            "负责川崎小蛮腰、青花瓷羽毛球服等新品在小红书、抖音、得物的内容推广，完成平台差异化定位、Brief 输出、达人筛选和投放节奏规划。",
            "月均统筹全平台预算近 10 万元，小红书单项目月均阅读量 60w+、抖音单项目月均阅读量 300w+，整体月度目标达成率 120%。",
            "统筹 4 位年框达人合作并负责内容审核与预算分配，月均爆文率 60%，项目 CPM 控制在 30 以内。",
            "协调供应商与执行团队推进样品流转与发布节点，达人笔记零延迟发布，样品流转效率提升 30%，当月 KPI 100% 完成。",
        ],
        y,
    )
    y = draw_job(
        draw,
        "玛俪琳（深圳）时尚服饰有限公司",
        "小红书推广专员",
        "2025.03 - 2025.08",
        [
            "负责 MARYLING、BORAAKSU、MARKFAST 三个子品牌的小红书博主合作全流程，覆盖策略设计、资源管理、内容品控及跨部门协同。",
            "通过“分层筛选 + 场景化内容”策略沉淀 120+ KOL/KOC，约 80% 粉丝重合，5 个月月均 seeding 115+，曝光精准度提升 80%。",
            "独立制定 Brief 并联动商品与仓库优化发货机制，样品流转效率提升 30%，优质内容占比提升至 55%。",
            "负责官号品牌文案与内容推广，持续提升品牌曝光与认知度，沉淀 300+ 条可复用的终端销售和二创素材。",
        ],
        y,
    )
    y = draw_job(
        draw,
        "深圳市美荟科技有限公司",
        "小红书推广实习生",
        "2022.07 - 2022.11",
        [
            "围绕 BLEO 品牌初创期推广，建立“场景 + 痛点 + 价值”内容框架，4 个月发布笔记 30+ 篇，爆文率 50%。",
            "拓展并维护近 80 位高匹配度博主，累计尾部与腰部 KOL/KOC 150+，样品丢失率 0%。",
            "合作内容平均互动量 5000-10000，多篇内容阅读量破 10000+，为品牌冷启动积累有效声量和素材。",
        ],
        y,
    )
    y = draw_job(
        draw,
        "Christian Dior",
        "零售助理",
        "2021.10 - 2022.06",
        [
            "维护 30+ VIC 和 Elite 客户，策划个性化活动，支持高净值客群服务与门店销售。",
            "订单准确率 99%，补货准确率 100%，参与三亚 Pop-up 店开业筹备，熟悉高端零售服务与活动执行。",
        ],
        y,
    )

    y = draw_section(draw, "教育背景", y)
    y = draw_bullet_list(
        draw,
        [
            "诺丁汉特伦特大学 | 奢侈品时尚品牌管理硕士 | 2023.09 - 2025.01",
            "诺丁汉特伦特大学 | 家具与产品设计学士 | 2019.09 - 2023.06",
        ],
        y,
        F_BODY,
        TEXT,
    )

    y = draw_section(draw, "语言与工具", y)
    y = draw_bullet_list(
        draw,
        [
            "英语：雅思 6 分，可阅读英文品牌资料并进行基础国际业务沟通",
            "粤语：良好",
            "工具：Excel（数据复盘）、InDesign（宣传素材）、剪映（品牌短视频与达人二创支持）",
        ],
        y,
        F_BODY,
        TEXT,
    )

    image.save(PNG_PATH, format="PNG")
    image.save(PDF_PATH, "PDF", resolution=300.0)


if __name__ == "__main__":
    build_resume()
