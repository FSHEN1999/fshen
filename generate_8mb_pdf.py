# -*- coding: utf-8 -*-
"""
生成8MB测试PDF文件
用于大文件测试场景
"""
import os
import random
import string
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def generate_random_text(length=1000):
    """生成随机文本"""
    chars = string.ascii_letters + string.digits + " ，。！？、；：""''（）【】《》"
    return ''.join(random.choice(chars) for _ in range(length))

def create_large_pdf(filename, target_size_mb=8):
    """
    创建指定大小的PDF文件

    Args:
        filename: 输出文件名
        target_size_mb: 目标文件大小（MB）
    """
    print(f"开始生成 {target_size_mb}MB 的PDF文件...")

    # 计算目标字节数
    target_size_bytes = target_size_mb * 1024 * 1024
    print(f"目标文件大小: {target_size_bytes:,} 字节")

    # 创建PDF文档
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch
    )

    styles = getSampleStyleSheet()

    # 创建自定义样式
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['h1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['h2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=12
    )

    text_style = ParagraphStyle(
        'CustomText',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        alignment=TA_LEFT
    )

    # 创建文档内容列表
    story = []

    # 添加封面
    story.append(Paragraph("8MB 测试文档", title_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"文件大小: {target_size_mb}MB", text_style))
    story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", text_style))
    story.append(Paragraph("本文档用于测试大文件处理能力", text_style))
    story.append(PageBreak())

    # 生成大量内容以达到目标大小
    current_size = 0
    page_count = 0
    section = 1
    paragraph_count = 0

    print("正在添加内容...")

    # 使用更直接的方法生成大量内容
    while current_size < target_size_bytes * 0.95:  # 95%的目标大小
        # 添加章节标题
        story.append(Paragraph(f"第 {section} 章 - 测试数据", heading_style))

        # 添加大量段落
        for i in range(100):  # 每章100个段落
            if paragraph_count >= 10000:  # 限制总段落数
                break

            # 生成不同长度的文本
            text_lengths = [500, 1000, 2000, 3000]
            text_length = random.choice(text_lengths)
            text = generate_random_text(text_length)

            # 随机应用样式
            if random.random() < 0.1:
                # 10%概率使用粗体
                para = Paragraph(f"<b>测试段落 {paragraph_count+1}:</b> {text}", text_style)
            elif random.random() < 0.1:
                # 10%概率使用斜体
                para = Paragraph(f"<i>测试段落 {paragraph_count+1}:</i> {text}", text_style)
            else:
                para = Paragraph(f"测试段落 {paragraph_count+1}: {text}", text_style)

            story.append(para)
            paragraph_count += 1

        # 添加表格
        for table_idx in range(3):  # 每章3个表格
            table_data = []
            headers = ["ID", "名称", "数值", "状态", "描述"]

            # 表头
            table_data.append(headers)

            # 生成表格内容
            for row in range(30):  # 每个表格30行
                row_data = [
                    str(random.randint(1000, 9999)),
                    f"项目{row+1}",
                    str(random.randint(1, 1000)),
                    random.choice(["正常", "警告", "错误"]),
                    generate_random_text(50)
                ]
                table_data.append(row_data)

            table = Table(table_data, colWidths=[0.6*inch, 1*inch, 0.8*inch, 0.8*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 0.2*inch))

        story.append(Spacer(1, 0.3*inch))

        # 每10页添加一个分页符
        if page_count > 0 and page_count % 10 == 0:
            story.append(PageBreak())

        # 检查当前文件大小
        if paragraph_count % 500 == 0:  # 每500个段落检查一次大小
            try:
                # 临时构建估算大小
                temp_doc = SimpleDocTemplate("temp_size_check.pdf", pagesize=A4)
                temp_doc.build(story[:len(story)//4])  # 只构建部分内容估算

                if os.path.exists("temp_size_check.pdf"):
                    current_size = os.path.getsize("temp_size_check.pdf")
                    os.remove("temp_size_check.pdf")

                    progress = (current_size / target_size_bytes) * 100
                    print(f"已生成: {current_size / (1024*1024):.2f} MB ({progress:.1f}%)")

                    if progress >= 95:
                        print("接近目标大小，停止添加内容")
                        break
            except Exception as e:
                print(f"检查大小时出错: {e}")
                break

        page_count += 1
        section += 1

        # 安全限制
        if page_count > 200:
            print("达到最大页数限制，停止生成")
            break

    # 构建最终文档
    print("\n正在构建最终PDF文档...")
    doc.build(story)

    # 检查最终文件大小
    final_size = os.path.getsize(filename)
    final_size_mb = final_size / (1024 * 1024)

    print(f"\n生成完成!")
    print(f"最终文件大小: {final_size_mb:.2f} MB")
    print(f"文件路径: {os.path.abspath(filename)}")
    print(f"总页数: {page_count}")
    print(f"总段落数: {paragraph_count}")

    return final_size_mb

if __name__ == "__main__":
    # 检查是否安装了reportlab
    try:
        import reportlab
    except ImportError:
        print("错误: 需要安装 reportlab 库")
        print("请运行: pip install reportlab")
        exit(1)

    # 输出文件名
    output_file = "8MB_test_document.pdf"

    # 生成8MB的PDF文件
    create_large_pdf(output_file, target_size_mb=8)