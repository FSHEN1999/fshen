#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成8MB的PDF测试文件
使用reportlab库生成内容丰富的PDF文档
"""

import os
import sys
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import random
import string
from datetime import datetime

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
        alignment=1  # TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['h2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=12
    )

    # 创建文档内容列表
    story = []

    # 添加封面
    story.append(Paragraph("大型PDF测试文档", title_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"文件大小: {target_size_mb}MB", styles['Normal']))
    story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Paragraph("本文档用于测试大文件处理能力", styles['Normal']))
    story.append(PageBreak())

    # 生成大量内容以达到目标大小
    page_count = 0
    section = 1

    print("正在添加内容...")

    # 直接生成固定数量的内容
    for section in range(1, 51):  # 50个章节
        # 添加章节标题
        story.append(Paragraph(f"第 {section} 章 - 测试内容", heading_style))

        # 添加大量段落内容
        for i in range(100):  # 每章100个段落
            # 生成长段落
            para_length = random.randint(3000, 8000)  # 更长的文本
            text = generate_random_text(para_length)
            para = Paragraph(f"段落 {i+1}: {text}", styles['Normal'])
            story.append(para)

        # 添加表格
        for table_idx in range(10):  # 每个章节10个表格
            table_data = []
            headers = ["ID", "名称", "描述", "数值", "状态", "详细信息", "备注", "时间戳"]

            # 表头
            table_data.append(headers)

            # 随机生成表格内容
            for row in range(50):  # 每个表格50行
                row_data = [
                    str(random.randint(1000, 9999)),
                    f"项目{row+1}",
                    generate_random_text(200),
                    str(random.randint(1, 1000)),
                    random.choice(["正常", "警告", "错误"]),
                    generate_random_text(400),
                    generate_random_text(100),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
                table_data.append(row_data)

            table = Table(table_data, colWidths=[0.4*inch, 0.8*inch, 1.2*inch, 0.6*inch, 0.6*inch, 1.8*inch, 1*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 0.2*inch))

        story.append(Spacer(1, 0.3*inch))

        # 每5章添加一个分页符
        if section % 5 == 0:
            story.append(PageBreak())

        page_count += 1

        print(f"已生成第 {section} 章...")

    # 构建最终文档
    print("\n正在构建最终PDF文档...")
    doc.build(story)

    # 检查最终文件大小
    final_size = os.path.getsize(filename)
    final_size_mb = final_size / (1024 * 1024)

    print(f"\n生成完成!")
    print(f"最终文件大小: {final_size_mb:.2f} MB")
    print(f"文件路径: {os.path.abspath(filename)}")
    print(f"总章节数: {section}")

    return final_size_mb

if __name__ == "__main__":
    # 检查是否安装了reportlab
    try:
        import reportlab
    except ImportError:
        print("错误: 需要安装 reportlab 库")
        print("请运行: pip install reportlab")
        sys.exit(1)

    # 输出文件名
    output_file = "8MB_test_document.pdf"

    # 生成8MB的PDF文件
    create_large_pdf(output_file, target_size_mb=8)