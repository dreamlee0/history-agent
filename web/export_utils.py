"""
对话导出工具 - 支持Markdown和PDF格式
"""
import os
from datetime import datetime
from typing import List, Dict
from io import BytesIO


def export_to_markdown(
    character_name: str,
    messages: List[Dict],
    character_info: Dict = None
) -> str:
    """导出对话为Markdown格式"""
    lines = []

    # 标题
    lines.append(f"# 与{character_name}的对话\n")

    # 时间
    lines.append(f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 人物信息
    if character_info:
        lines.append("## 人物信息\n")
        lines.append(f"- **朝代**: {character_info.get('dynasty', '未知')}")
        lines.append(f"- **身份**: {character_info.get('title', '未知')}")
        lines.append(f"- **生卒年**: {character_info.get('years', '未知')}\n")

    # 对话内容
    lines.append("## 对话记录\n")
    lines.append("---\n")

    for msg in messages:
        role = "👤 用户" if msg["role"] == "user" else f"🎭 {character_name}"
        content = msg["content"]
        lines.append(f"### {role}\n")
        lines.append(f"{content}\n")

        # 参考来源
        if "sources" in msg and msg["sources"]:
            lines.append("*参考资料*: " + " | ".join([
                src.get("title", "未知") for src in msg["sources"]
            ]) + "\n")

        lines.append("---\n")

    # 页脚
    lines.append("\n*由「历史人物对话」系统生成*\n")

    return "\n".join(lines)


def export_to_pdf(
    character_name: str,
    messages: List[Dict],
    character_info: Dict = None
) -> bytes:
    """导出对话为PDF格式"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        raise ImportError("请安装reportlab: pip install reportlab")

    # 创建PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # 样式
    styles = getSampleStyleSheet()

    # 尝试注册中文字体
    try:
        # 尝试常见的中文字体路径
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "C:/Windows/Fonts/msyh.ttc",
        ]
        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Chinese', font_path))
                font_registered = True
                break

        if font_registered:
            title_style = ParagraphStyle(
                'ChineseTitle',
                parent=styles['Title'],
                fontName='Chinese',
                fontSize=24,
                alignment=TA_CENTER,
                spaceAfter=30
            )
            heading_style = ParagraphStyle(
                'ChineseHeading',
                parent=styles['Heading2'],
                fontName='Chinese',
                fontSize=14,
                spaceAfter=12
            )
            body_style = ParagraphStyle(
                'ChineseBody',
                parent=styles['Normal'],
                fontName='Chinese',
                fontSize=11,
                leading=18,
                spaceAfter=12
            )
            meta_style = ParagraphStyle(
                'ChineseMeta',
                parent=styles['Normal'],
                fontName='Chinese',
                fontSize=10,
                textColor='gray',
                spaceAfter=6
            )
        else:
            raise Exception("No Chinese font found")
    except:
        # 回退到默认样式
        title_style = styles['Title']
        heading_style = styles['Heading2']
        body_style = styles['Normal']
        meta_style = styles['Normal']

    # 构建内容
    story = []

    # 标题
    story.append(Paragraph(f"与{character_name}的对话", title_style))
    story.append(Spacer(1, 0.5*cm))

    # 时间
    story.append(Paragraph(
        f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        meta_style
    ))
    story.append(Spacer(1, 1*cm))

    # 人物信息
    if character_info:
        story.append(Paragraph("人物信息", heading_style))
        story.append(Paragraph(
            f"朝代: {character_info.get('dynasty', '未知')}  |  "
            f"身份: {character_info.get('title', '未知')}  |  "
            f"生卒年: {character_info.get('years', '未知')}",
            body_style
        ))
        story.append(Spacer(1, 1*cm))

    # 对话内容
    story.append(Paragraph("对话记录", heading_style))
    story.append(Spacer(1, 0.5*cm))

    for msg in messages:
        role = "👤 用户" if msg["role"] == "user" else f"🎭 {character_name}"
        content = msg["content"].replace("\n", "<br/>")

        story.append(Paragraph(f"<b>{role}</b>", body_style))
        story.append(Paragraph(content, body_style))

        if "sources" in msg and msg["sources"]:
            sources = " | ".join([src.get("title", "未知") for src in msg["sources"]])
            story.append(Paragraph(f"<i>参考资料: {sources}</i>", meta_style))

        story.append(Spacer(1, 0.3*cm))

    # 生成PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def get_download_filename(character_name: str, ext: str) -> str:
    """生成下载文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = character_name.replace("/", "_").replace("\\", "_")
    return f"对话_{safe_name}_{timestamp}.{ext}"
