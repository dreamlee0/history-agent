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
        role = "用户" if msg["role"] == "user" else character_name
        content = msg["content"]
        lines.append(f"### {role}\n")
        lines.append(f"{content}\n")

        # 参考来源（url 非空时导出为可点击链接文本）
        if "sources" in msg and msg["sources"]:
            refs = []
            for src in msg["sources"]:
                title = src.get("title", "未知")
                url = src.get("url", "")
                refs.append(f"[{title}]({url})" if url else title)
            lines.append("*参考资料*: " + " | ".join(refs) + "\n")

        lines.append("---\n")

    # 页脚
    lines.append("\n*由「历史人物对话」系统生成*\n")

    return "\n".join(lines)


def _register_chinese_font():
    """注册中文字体，返回 (font_name, is_bold_supported)"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 尝试系统字体路径
    font_paths = [
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYi"),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WenQuanYi"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/System/Library/Fonts/PingFang.ttc", "PingFang"),
        ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
        ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
    ]

    for font_path, font_name in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                return font_name
            except Exception:
                continue

    return None


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
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase import pdfmetrics
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

    # 注册中文字体 - 优先使用系统字体，回退到 CID 字体。
    # system_font_available 记录是否存在系统字体，供导出失败时给出安装提示（M10）。
    font_name = _register_chinese_font()
    system_font_available = bool(font_name)
    if not font_name:
        # 使用 reportlab 内置的 CID 中文字体（无需外部字体文件）
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        font_name = 'STSong-Light'

    # 样式
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ChineseTitle',
        parent=styles['Title'],
        fontName=font_name,
        fontSize=22,
        alignment=TA_CENTER,
        spaceAfter=24
    )
    heading_style = ParagraphStyle(
        'ChineseHeading',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=14,
        spaceAfter=12
    )
    body_style = ParagraphStyle(
        'ChineseBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=11,
        leading=18,
        spaceAfter=12
    )
    meta_style = ParagraphStyle(
        'ChineseMeta',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        textColor='gray',
        spaceAfter=6
    )

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
        role = "用户" if msg["role"] == "user" else character_name
        # 清理内容中的特殊字符
        content = msg["content"].replace("\n", "<br/>")
        # 转义 XML 特殊字符
        content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # 还原我们插入的 <br/>
        content = content.replace("&lt;br/&gt;", "<br/>")

        story.append(Paragraph(f"<b>{role}</b>", body_style))
        story.append(Paragraph(content, body_style))

        if "sources" in msg and msg["sources"]:
            refs = []
            for src in msg["sources"]:
                title = src.get("title", "未知")
                url = src.get("url", "")
                # 转义 XML 特殊字符，防止标题/URL 破坏 reportlab 段落
                safe_title = (
                    title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                # url 非空时作为链接文本一并导出（M6）
                refs.append(f"{safe_title} ({url})" if url else safe_title)
            sources = " | ".join(refs)
            story.append(Paragraph(f"<i>参考资料: {sources}</i>", meta_style))

        story.append(Spacer(1, 0.3*cm))

    try:
        # 生成PDF
        doc.build(story)
    except Exception as e:
        # 导出失败时，若系统缺少中文字体则附上安装提示（M10），
        # 避免用户面对裸异常无从下手。
        hint = ""
        if not system_font_available:
            hint = ("；系统中文字体缺失，请安装文泉驿（Linux: apt install fonts-wqy-zenhei）"
                    "/ 微软雅黑（Windows）")
        raise Exception(f"PDF导出失败: {e}{hint}") from e
    buffer.seek(0)
    return buffer.getvalue()


def get_download_filename(character_name: str, ext: str) -> str:
    """生成下载文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = character_name.replace("/", "_").replace("\\", "_")
    return f"对话_{safe_name}_{timestamp}.{ext}"
