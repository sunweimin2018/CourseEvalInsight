import os
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.platypus.flowables import KeepTogether, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from .module_docx import _generate_chart_image

FONT_NAME = 'simsun'
FONT_SIZE = 10
FONT_SIZE_TITLE = 18
FONT_SIZE_H1 = 14
FONT_SIZE_H2 = 12
FONT_SIZE_TABLE = 9

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    candidates = [
        'C:/Windows/Fonts/simsun.ttc',
        'C:/Windows/Fonts/SIMSUN.TTC',
        'C:/Windows/Fonts/simsun.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/System/Library/Fonts/Songti.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, path, subfontIndex=0))
                registerFontFamily(FONT_NAME, normal=FONT_NAME, bold=FONT_NAME,
                                   italic=FONT_NAME, boldItalic=FONT_NAME)
                break
            except Exception:
                continue
    _fonts_registered = True


def _styles():
    _register_fonts()
    return {
        'title': ParagraphStyle(
            'CNTitle', fontName=FONT_NAME, fontSize=FONT_SIZE_TITLE,
            alignment=TA_CENTER, spaceAfter=10 * mm, leading=26,
        ),
        'h1': ParagraphStyle(
            'CNH1', fontName=FONT_NAME, fontSize=FONT_SIZE_H1,
            spaceBefore=8 * mm, spaceAfter=4 * mm, leading=20,
        ),
        'h2': ParagraphStyle(
            'CNH2', fontName=FONT_NAME, fontSize=FONT_SIZE_H2,
            spaceBefore=5 * mm, spaceAfter=2 * mm, leading=17,
        ),
        'body': ParagraphStyle(
            'CNBody', fontName=FONT_NAME, fontSize=FONT_SIZE,
            leading=16, spaceAfter=2 * mm,
        ),
        'cell': ParagraphStyle(
            'CNCell', fontName=FONT_NAME, fontSize=FONT_SIZE_TABLE,
            leading=13, alignment=TA_LEFT,
        ),
        'cell_bold': ParagraphStyle(
            'CNCellBold', fontName=FONT_NAME, fontSize=FONT_SIZE_TABLE,
            leading=13, alignment=TA_LEFT,
        ),
        'cell_center': ParagraphStyle(
            'CNCellCenter', fontName=FONT_NAME, fontSize=FONT_SIZE_TABLE,
            leading=13, alignment=TA_CENTER,
        ),
    }


def _p(text, style):
    return Paragraph(text, style)


def _build_info_table(info, s):
    """Build the 7-row course basic info table as a reportlab Table."""
    label_style = s['cell_bold']
    value_style = s['cell']

    def L(t):
        return _p(t, label_style)

    def V(t):
        return _p(str(t), value_style)

    data = [
        [L('课程名称：'), V(info.get('course_name', '')), L('修课人数：'), V(str(info.get('student_count', '')))],
        [L('课程编号：'), V(info.get('course_code', '')), L('课序号：'), V(str(info.get('course_seq', '')))],
        [L('授课班级：'), V(info.get('teaching_class', '')), L('学时数：'), V(str(info.get('total_hours', '')))],
        [L('选用教材：'), V(info.get('textbook', '')), L('学分：'), V(str(info.get('credits', '')))],
        [L('开课院系：'), V(info.get('department', '')), L('授课教师：'), V(str(info.get('teacher', '')))],
        [L('课程性质：'), V(info.get('course_nature', '')), '', ''],
        [L('课程类型：'), V(info.get('course_type', '')), '', ''],
    ]
    # SPAN for merged cells in rows 5,6: col 1 spans cols 1-3
    spans = [
        ('SPAN', (1, 5), (3, 5)),  # row 5, cols 1-3 merged
        ('SPAN', (1, 6), (3, 6)),  # row 6, cols 1-3 merged
    ]

    col_widths = [70, 160, 70, 160]
    tbl = Table(data, colWidths=col_widths, repeatRows=0)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ] + spans))
    return tbl


def _build_blocks_table(block, s):
    """Build a reportlab Table from a grid block, preserving merged cells."""
    grid = block['grid']
    num_cols = block['num_cols']
    num_rows = len(grid)

    cell_style = s['cell']
    cell_bold = s['cell_bold']

    # Build flat data array and SPAN commands
    data = []
    spans = []
    for r in range(num_rows):
        row_data = []
        c = 0
        while c < num_cols:
            cell = grid[r][c] if c < len(grid[r]) else None
            if cell is None:
                row_data.append('')
                c += 1
            else:
                style = cell_bold if r == 0 else cell_style
                row_data.append(_p(cell['text'], style))
                if cell['colspan'] > 1 or cell['rowspan'] > 1:
                    end_r = r + cell['rowspan'] - 1
                    end_c = c + cell['colspan'] - 1
                    if end_r >= r or end_c >= c:
                        spans.append(('SPAN', (c, r), (end_c, end_r)))
                c += cell['colspan']
        data.append(row_data)

    if not data:
        return None

    available_width = 160 * mm
    col_w = available_width / num_cols

    tbl = Table(data, colWidths=[col_w] * num_cols, repeatRows=0)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ] + spans))
    return tbl


def _build_dist_table(stats, s):
    """Build the score distribution sub-table."""
    cell_s = s['cell_center']
    cell_bold = s['cell_bold']
    dist = stats['distribution']

    data = [
        [_p('类别', cell_bold), _p('人数', cell_bold), _p('占比', cell_bold)],
    ]
    total = stats['count']
    for key, d in dist.items():
        pct = round(d['count'] / total * 100, 1) if total else 0
        data.append([
            _p(d['label'], cell_s),
            _p(str(d['count']), cell_s),
            _p(f'{pct}%', cell_s),
        ])

    tbl = Table(data, colWidths=[120, 80, 80], repeatRows=1)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E2F3')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tbl


def generate_pdf(report_name, report_data):
    """Generate PDF from report data and return BytesIO buffer."""
    _register_fonts()
    s = _styles()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=report_name,
    )

    story = []

    # ── Title ───────────────────────────────────────────────────────────
    story.append(_p(report_name, s['title']))

    # ── Module 1: Course Basic Info Table ───────────────────────────────
    story.append(_p('一、课程基本信息表', s['h1']))
    info = report_data.get('module_1_course_info', {})
    story.append(_build_info_table(info, s))
    story.append(Spacer(1, 4 * mm))

    # ── Module 2: Course Objectives ─────────────────────────────────────
    story.append(_p('二、课程目标', s['h1']))
    obj = report_data.get('module_2_objectives', '未填写')
    for line in obj.split('\n'):
        if line.strip():
            story.append(_p(line.strip(), s['body']))

    # ── Module 3: Evaluation Standards ──────────────────────────────────
    story.append(_p('三、课程评价标准', s['h1']))
    eval_data = report_data.get('module_3_evaluation_standards', '未填写')
    if isinstance(eval_data, list):
        for block in eval_data:
            if block['type'] == 'paragraph':
                story.append(_p(block['text'], s['body']))
            elif block['type'] == 'table':
                tbl = _build_blocks_table(block, s)
                if tbl:
                    story.append(tbl)
                    story.append(Spacer(1, 3 * mm))
    else:
        for line in str(eval_data).split('\n'):
            if line.strip():
                story.append(_p(line.strip(), s['body']))

    # ── Module 4: Evaluation Results ────────────────────────────────────
    story.append(_p('四、课程评价结果', s['h1']))
    eval_results = report_data.get('module_4_evaluation_results', {})
    sections = eval_results.get('sections')

    if sections:
        # Top-level fallback alert
        if eval_results.get('fallback'):
            story.append(_p(
                '⚠ 未从课程大纲中提取到考核评价标准分数段定义，已使用默认分数段（优秀/良好/中等/及格/不及格）',
                s['body'],
            ))

        for section in sections:
            # Build heading with weight info
            title = section['col_name']
            if section.get('weight_pct'):
                title += f'（占总评{section["weight_pct"]}%）'
            story.append(_p(title, s['h2']))

            # Normalization note
            if section.get('is_weighted'):
                story.append(_p('注：该列成绩已由折算后分数归一化至百分制', s['body']))

            # Segment source note
            src = section.get('segment_source', '')
            if src == 'fallback':
                story.append(_p('注：该列使用默认分数段', s['body']))
            elif src == 'default':
                story.append(_p('注：该列使用系统默认分数段', s['body']))

            story.append(_p(section.get('description_line_1', ''), s['body']))
            story.append(_p(section.get('description_line_2', ''), s['body']))

            # Build distribution table matching Word format
            segments = section.get('segments', [])
            if segments:
                num_cols = len(segments) + 2  # 类别 + segments + 平均分
                col_widths = [60] + [int(340 / (num_cols - 1))] * (num_cols - 1)

                # Header row: 类别 | segment labels... | 平均分
                header_row = [_p('类别', s['cell_bold'])]
                for seg in segments:
                    header_row.append(_p(seg['label'], s['cell_center']))
                header_row.append(_p('平均分', s['cell_bold']))

                # Row 1: 人数 | counts... | avg_score
                count_row = [_p('人数', s['cell_bold'])]
                for seg in segments:
                    count_row.append(_p(str(seg['count']), s['cell_center']))
                count_row.append(_p(str(section['avg_score']), s['cell_center']))

                # Row 2: 比例% | pcts... | 100
                pct_row = [_p('比例%', s['cell_bold'])]
                for seg in segments:
                    pct_row.append(_p(f"{seg['pct']}%", s['cell_center']))
                pct_row.append(_p('100', s['cell_center']))

                dist_data = [header_row, count_row, pct_row]
                tbl = Table(dist_data, colWidths=col_widths, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E2F3')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 2 * mm))

            # Chart image (best-effort)
            try:
                chart_buf = _generate_chart_image(section)
                if chart_buf:
                    img = Image(chart_buf, width=140 * mm, height=80 * mm)
                    story.append(img)
                    caption = _p(f'图：学生{section["col_name"]}成绩分布图', s['body'])
                    caption.alignment = TA_CENTER
                    story.append(caption)
                    story.append(Spacer(1, 3 * mm))
            except Exception:
                pass

            # Stats
            stats = section['stats']
            story.append(_p(
                f"参考人数：{stats['count']}　缺考人数：{stats['missing']}　"
                f"最高分：{stats['max']}　最低分：{stats['min']}　"
                f"平均分：{stats['avg']}　中位数：{stats['median']}　"
                f"标准差：{stats['stdev']}　及格率：{stats['pass_rate']}%",
                s['body'],
            ))

            # AI summary
            ai_summary = section.get('ai_summary', '')
            if ai_summary:
                story.append(_p(ai_summary, s['body']))

            story.append(Spacer(1, 5 * mm))
    else:
        # Legacy grade_analysis format
        grade_analysis = eval_results.get('grade_analysis', {})
        if grade_analysis:
            for col_name, stats in grade_analysis.items():
                story.append(_p(col_name, s['h2']))
                lines = [
                    f"参考人数：{stats['count']}　缺考人数：{stats['missing']}　"
                    f"最高分：{stats['max']}　最低分：{stats['min']}　"
                    f"平均分：{stats['avg']}　中位数：{stats['median']}　"
                    f"标准差：{stats['stdev']}　及格率：{stats['pass_rate']}%",
                ]
                for line in lines:
                    story.append(_p(line, s['body']))
                story.append(_p('成绩分布：', s['body']))
                story.append(_build_dist_table(stats, s))
                story.append(Spacer(1, 3 * mm))
        else:
            story.append(_p('暂无成绩数据', s['body']))

    # ── Module 5: Improvement Plan ──────────────────────────────────────
    story.append(_p('五、课程持续改进方案及措施', s['h1']))
    plan = report_data.get('module_5_improvement_plan', '待后续版本实现')
    if isinstance(plan, dict):
        # 4.1
        story.append(_p('4.1 连续两年课程评价结果系统地纳入课程持续改进的措施及其效果描述', s['h2']))
        for line in plan.get('part1', '').split('\n'):
            if line.strip():
                story.append(_p(line.strip(), s['body']))

        # 4.2
        story.append(_p('4.2 本年度课程教学环节发现的问题、相应持续改进的措施以及描述预期将可能达到的效果', s['h2']))
        part2 = plan.get('part2', {})
        if isinstance(part2, dict):
            story.append(_p('(1) 存在的问题', s['h2']))
            for line in part2.get('problems', '').split('\n'):
                if line.strip():
                    story.append(_p(line.strip(), s['body']))
            story.append(_p('(2) 持续改进措施', s['h2']))
            for line in part2.get('measures', '').split('\n'):
                if line.strip():
                    story.append(_p(line.strip(), s['body']))
            story.append(_p('(3) 预期效果', s['h2']))
            for line in part2.get('expected_effects', '').split('\n'):
                if line.strip():
                    story.append(_p(line.strip(), s['body']))
        else:
            story.append(_p(str(part2), s['body']))

        # 4.3
        story.append(_p('4.3 其他可用的协助持续改进的资源', s['h2']))
        for line in plan.get('part3', '').split('\n'):
            if line.strip():
                story.append(_p(line.strip(), s['body']))
    else:
        for line in str(plan).split('\n'):
            if line.strip():
                story.append(_p(line.strip(), s['body']))

    # Signature lines
    from datetime import date
    today = date.today()
    today_str = f'{today.year}.{today.month}.{today.day}'
    story.append(Spacer(1, 10 * mm))
    for label in ('任课教师签名：', '责任教授或系主任签名：'):
        story.append(_p(f'{label}                日期：{today_str}', s['body']))

    doc.build(story)
    buf.seek(0)
    return buf
