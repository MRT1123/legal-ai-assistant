"""
文件解析服务
支持多种文件格式的文本提取：PDF、DOCX、TXT、MD
用于合同审查功能的文件上传
"""

import os


def parse_file(file_path: str) -> str:
    """根据文件扩展名选择合适的解析器，提取文本内容
    
    支持的格式：
    - .pdf  → PyPDF2 库解析
    - .docx → python-docx 库解析
    - .txt  → 直接读取（UTF-8 优先，失败则用 GBK）
    - .md   → 直接读取（同 .txt）
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        return _parse_pdf(file_path)
    elif ext == '.docx':
        return _parse_docx(file_path)
    elif ext in ('.txt', '.md'):
        return _parse_text(file_path)
    else:
        raise ValueError(f"不支持的文件格式：{ext}")


def _parse_pdf(file_path: str) -> str:
    """解析 PDF 文件，提取所有页面的文本"""
    from PyPDF2 import PdfReader
    
    reader = PdfReader(file_path)
    text_parts = []
    
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    
    result = "\n".join(text_parts).strip()
    if not result:
        raise ValueError("PDF 文件中未提取到任何文本内容，可能是扫描件或图片 PDF")
    return result


def _parse_docx(file_path: str) -> str:
    """解析 Word 文档（.docx），提取所有段落文本"""
    from docx import Document
    
    doc = Document(file_path)
    text_parts = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    
    result = "\n".join(text_parts).strip()
    if not result:
        raise ValueError("Word 文档中未找到任何文本内容")
    return result


def _parse_text(file_path: str) -> str:
    """解析纯文本文件（.txt / .md），尝试 UTF-8 编码，失败则用 GBK"""
    # 先尝试 UTF-8
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # 中文 Windows 环境常见 GBK 编码
        with open(file_path, 'r', encoding='gbk') as f:
            return f.read()
