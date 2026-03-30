# -*- coding: utf-8 -*-
"""
创建8MB测试文件的最简单方法
直接写入二进制数据以快速达到目标大小
"""

import os
from datetime import datetime

def create_8mb_file():
    """直接创建8MB的测试文件"""
    print("开始创建8MB测试文件...")

    # 输出文件路径
    output_file = "8MB_test_file.pdf"

    # 计算需要写入的字节数（8MB）
    target_size = 8 * 1024 * 1024

    # 创建文件并写入数据
    with open(output_file, 'wb') as f:
        # 写入PDF文件头（最小PDF格式）
        pdf_header = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
  /Font <<
    /F1 <<
      /Type /Font
      /Subtype /Type1
      /BaseFont /Helvetica
    >>
  >>
>>
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 24 Tf
50 750 Td
(Test Document) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
343
%%EOF"""

        # 写入PDF头
        f.write(pdf_header)

        # 写入大量重复数据以达到8MB
        remaining_size = target_size - len(pdf_header)
        chunk_size = 1024 * 1024  # 1MB chunks

        print(f"PDF头大小: {len(pdf_header)} 字节")
        print(f"需要填充: {remaining_size:,} 字节")

        # 写入填充数据
        chunk = b"0" * chunk_size
        chunks_written = 0

        while remaining_size > 0:
            write_size = min(chunk_size, remaining_size)
            if chunks_written % 10 == 0:
                print(f"已写入: {chunks_written * chunk_size / (1024*1024):.1f} MB")

            f.write(chunk[:write_size])
            remaining_size -= write_size
            chunks_written += 1

    # 验证文件大小
    actual_size = os.path.getsize(output_file)
    actual_size_mb = actual_size / (1024 * 1024)

    print(f"\n创建完成!")
    print(f"目标大小: 8.00 MB")
    print(f"实际大小: {actual_size_mb:.2f} MB")
    print(f"文件路径: {os.path.abspath(output_file)}")
    print(f"文件名: {output_file}")

    return output_file

if __name__ == "__main__":
    create_8mb_file()