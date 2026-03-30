#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建8MB的PDF测试文件 - 简化版本
"""

import os
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import random
import string
from datetime import datetime

def generate_large_pdf(filename, target_size_mb=8):
    """生成指定大小的PDF文件"""
    print(f"开始生成 {target_size_mb}MB 的PDF文件...")

    # 计算目标大小（字节）
    target_size = target_size_mb * 1024 * 1024
    print(f"目标大小: {target_size:,} 字节")

    # 创建PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    # 设置字体
    p.setFont("Helvetica", 12)

    # 初始化
    current_size = 0
    page_count = 0
    line_count = 0
    lines_per_page = 45  # 每页行数

    # 生成文本内容
    def generate_text():
        chars = string.ascii_letters + string.digits + " ，。！？、；：""''（）【】《》"
        return ''.join(random.choice(chars) for _ in range(80))

    print("正在生成内容...")

    while current_size < target_size:
        # 开始新页面
        if line_count >= lines_per_page:
            p.showPage()
            page_count += 1
            line_count = 0

            # 显示进度
            if page_count % 10 == 0:
                # 估算当前大小
                buffer.seek(0, 2)  # 移动到文件末尾
                current_size = buffer.tell()
                progress = (current_size / target_size) * 100
                print(f"进度: {page_count} 页, {current_size/1024/1024:.2f} MB ({progress:.1f}%)")

        # 添加内容到页面
        y_pos = 750 - (line_count * 15)  # 每行15磅

        # 标题
        if line_count == 0:
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, y_pos, f"第 {page_count + 1} 页 - PDF测试文档")
            line_count += 1
            y_pos -= 20

            p.setFont("Helvetica", 12)

        # 正文内容
        text = generate_text()

        # 随机添加格式
        if random.random() < 0.1:  # 10%粗体
            p.setFont("Helvetica-Bold", 12)
        elif random.random() < 0.1:  # 10%斜体
            p.setFont("Helvetica-Oblique", 12)
        else:
            p.setFont("Helvetica", 12)

        # 添加文本（自动换行）
        text_object = p.beginText(50, y_pos)
        text_object.textLines(text)
        p.drawText(text_object)

        line_count += 1

        # 更新文件大小估算
        buffer.seek(0, 2)
        current_size = buffer.tell()

    # 完成文档
    p.showPage()
    page_count += 1

    # 保存PDF
    p.save()

    # 获取最终数据并保存到文件
    final_data = buffer.getvalue()

    # 写入文件
    with open(filename, 'wb') as f:
        f.write(final_data)

    # 获取最终文件大小
    final_size = len(final_data)
    final_size_mb = final_size / (1024 * 1024)

    print(f"\n生成完成!")
    print(f"最终文件大小: {final_size_mb:.2f} MB")
    print(f"总页数: {page_count}")
    print(f"文件路径: {os.path.abspath(filename)}")

    return final_size_mb, page_count

if __name__ == "__main__":
    # 创建8MB的PDF文件
    filename = "8MB_test_document.pdf"

    try:
        size, pages = generate_large_pdf(filename, 8)
        print(f"\n✅ 成功创建8MB测试PDF文件!")
    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        # 创建一个简单的备用文件
        print("\n创建备用文件...")
        with open("8MB_test_document.pdf", 'wb') as f:
            # 写入足够的数据达到8MB
            data = b"X" * 8388608  # 8MB
            f.write(data)
        print("✅ 已创建8MB的测试文件（纯文本格式）")