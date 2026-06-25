"""Single-module Word document export functions.

Each function takes a ReportRecord and returns a BytesIO buffer containing
a standalone .docx file for that module.
"""

from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _setup_matplotlib_chinese():
    """Configure matplotlib for Chinese font rendering. Call once."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    # Try to find a Chinese font
    candidates = [
        'C:/Windows/Fonts/simsun.ttc',
        'C:/Windows/Fonts/SIMSUN.TTC',
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/MSYH.TTC',
        'C:/Windows/Fonts/simhei.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/System/Library/Fonts/Songti.ttc',
    ]
    for path in candidates:
        import os
        if os.path.exists(path):
            return FontProperties(fname=path, size=10)
    return None


_chinese_font = None


def _get_chinese_font():
    global _chinese_font
    if _chinese_font is None:
        _chinese_font = _setup_matplotlib_chinese()
    return _chinese_font


def _generate_chart_image(section):
    """Generate a bar chart image for a grade section. Returns BytesIO or None."""
    import matplotlib.pyplot as plt

    segments = section.get('segments', [])
    if not segments:
        return None

    labels = [s['label'] for s in segments]
    counts = [s['count'] for s in segments]
    col_name = section.get('col_name', '')

    font = _get_chinese_font()
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, counts, color='#409eff', edgecolor='white')
    ax.set_title(f'学生{col_name}成绩分布图', fontproperties=font, fontsize=14)
    ax.set_xlabel('分数段', fontproperties=font, fontsize=11)
    ax.set_ylabel('人数', fontproperties=font, fontsize=11)

    # Set tick labels with font
    if font:
        for label in ax.get_xticklabels():
            label.set_fontproperties(font)
        for label in ax.get_yticklabels():
            label.set_fontproperties(font)

    # Add count labels on top of bars
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(count), ha='center', va='bottom', fontsize=10)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf


def _setup_document(report):
    """Create a fresh Document with default Song Ti font and centered title."""
    doc = Document()
    default_style = doc.styles['Normal']
    default_style.font.name = '宋体'
    default_style.font.size = Pt(12)

    title = doc.add_heading(report.report_name, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.name = '宋体'
        run.font.size = Pt(16)

    return doc


def _run_font(run, font_name='宋体', font_size=Pt(12)):
    run.font.name = font_name
    run.font.size = font_size
    return run


def _set_cell(cell, text, bold=False):
    cell.text = ''
    run = cell.paragraphs[0].add_run(str(text))
    _run_font(run)
    if bold:
        run.bold = True


def _add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        _run_font(run)
    return h


def _add_paragraph(doc, text):
    p = doc.add_paragraph(str(text))
    for run in p.runs:
        _run_font(run)
    return p


def _to_buffer(doc):
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ── Module 1: Course Basic Info Table ───────────────────────────────────────

def export_module_1_docx(report):
    doc = _setup_document(report)
    rd = report.report_data
    info = rd.get('module_1_course_info', {})
    _add_heading(doc, '一、课程基本信息表')

    table = doc.add_table(rows=7, cols=4, style='Table Grid')
    rows_data = [
        ['课程名称：', info.get('course_name', ''), '修课人数：', str(info.get('student_count', ''))],
        ['课程编号：', info.get('course_code', ''), '课序号：', str(info.get('course_seq', ''))],
        ['授课班级：', info.get('teaching_class', ''), '学时数：', str(info.get('total_hours', ''))],
        ['选用教材：', info.get('textbook', ''), '学分：', str(info.get('credits', ''))],
        ['开课院系：', info.get('department', ''), '授课教师：', str(info.get('teacher', ''))],
    ]
    for r_idx, (lbl1, val1, lbl2, val2) in enumerate(rows_data):
        _set_cell(table.cell(r_idx, 0), lbl1, bold=True)
        _set_cell(table.cell(r_idx, 1), val1)
        _set_cell(table.cell(r_idx, 2), lbl2, bold=True)
        _set_cell(table.cell(r_idx, 3), val2)

    _set_cell(table.cell(5, 0), '课程性质：', bold=True)
    table.cell(5, 1).merge(table.cell(5, 3))
    _set_cell(table.cell(5, 1), info.get('course_nature', ''))

    _set_cell(table.cell(6, 0), '课程类型：', bold=True)
    table.cell(6, 1).merge(table.cell(6, 3))
    _set_cell(table.cell(6, 1), info.get('course_type', ''))

    return _to_buffer(doc)


# ── Module 2: Course Objectives ─────────────────────────────────────────────

def export_module_2_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '二、课程目标')
    _add_paragraph(doc, report.report_data.get('module_2_objectives', '未填写'))
    return _to_buffer(doc)


# ── Module 3: Evaluation Standards ──────────────────────────────────────────

def export_module_3_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '三、课程评价标准')

    eval_data = report.report_data.get('module_3_evaluation_standards', '未填写')
    if isinstance(eval_data, list):
        for block in eval_data:
            if block['type'] == 'paragraph':
                _add_paragraph(doc, block['text'])
            elif block['type'] == 'table':
                grid = block['grid']
                num_cols = block['num_cols']
                if not grid or num_cols == 0:
                    continue
                num_rows = len(grid)
                tbl = doc.add_table(rows=num_rows, cols=num_cols, style='Table Grid')
                for r in range(num_rows):
                    for c in range(num_cols):
                        cell_data = grid[r][c]
                        if cell_data is None:
                            continue
                        cell = tbl.cell(r, c)
                        _set_cell(cell, cell_data['text'], bold=(r == 0))
                        if cell_data['colspan'] > 1 or cell_data['rowspan'] > 1:
                            end_r = r + cell_data['rowspan'] - 1
                            end_c = c + cell_data['colspan'] - 1
                            cell.merge(tbl.cell(end_r, end_c))
    else:
        _add_paragraph(doc, eval_data)

    return _to_buffer(doc)


# ── Module 4: Evaluation Results ────────────────────────────────────────────

def _render_module_4_to_docx(doc, module_4_data):
    """Render Module 4 sections into a docx Document. Shared by standalone export
    and merge export in views.py."""
    sections = module_4_data.get('sections')

    if sections:
        for section in sections:
            _add_heading(doc, section['col_name'], level=2)
            _add_paragraph(doc, section['description_line_1'])
            _add_paragraph(doc, section['description_line_2'])

            segments = section['segments']
            num_cols = len(segments) + 2
            table = doc.add_table(rows=3, cols=num_cols, style='Table Grid')

            # Row 0: 类别 | segment labels... | 平均分
            _set_cell(table.cell(0, 0), '类别', bold=True)
            for ci, seg in enumerate(segments):
                _set_cell(table.cell(0, ci + 1), seg['label'], bold=True)
            _set_cell(table.cell(0, num_cols - 1), '平均分', bold=True)

            # Row 1: 人数 | counts... | avg_score
            _set_cell(table.cell(1, 0), '人数')
            for ci, seg in enumerate(segments):
                _set_cell(table.cell(1, ci + 1), str(seg['count']))
            _set_cell(table.cell(1, num_cols - 1), str(section['avg_score']))

            # Row 2: 比例% | pcts... | 100
            _set_cell(table.cell(2, 0), '比例%')
            for ci, seg in enumerate(segments):
                _set_cell(table.cell(2, ci + 1), f"{seg['pct']}%")
            _set_cell(table.cell(2, num_cols - 1), '100')

            # Chart image (best-effort, skip on failure)
            try:
                chart_buf = _generate_chart_image(section)
                if chart_buf:
                    chart_paragraph = doc.add_paragraph()
                    chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    chart_run = chart_paragraph.add_run()
                    chart_run.add_picture(chart_buf, width=Inches(5.5))
                    caption = doc.add_paragraph(f'图：学生{section["col_name"]}成绩分布图')
                    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in caption.runs:
                        _run_font(run, font_size=Pt(10))
            except Exception:
                pass  # chart generation is best-effort

            # Stats summary
            s = section['stats']
            p = doc.add_paragraph()
            for label, val in [
                ('参考人数：', s['count']),
                ('缺考人数：', s['missing']),
                ('最高分：', s['max']),
                ('最低分：', s['min']),
                ('平均分：', s['avg']),
                ('中位数：', s['median']),
                ('标准差：', s['stdev']),
            ]:
                _run_font(p.add_run(f'{label}{val}　　'))
            _run_font(p.add_run(f'及格率：{s["pass_rate"]}%'))

            # AI summary
            ai_summary = section.get('ai_summary', '')
            if ai_summary:
                _add_paragraph(doc, '')
                _add_paragraph(doc, ai_summary)
        return

    # Legacy fallback: old-format grade_analysis
    grade_analysis = module_4_data.get('grade_analysis', {})
    if not grade_analysis:
        _add_paragraph(doc, '暂无成绩数据')
        return

    for col_name, stats in grade_analysis.items():
        _add_heading(doc, col_name, level=2)

        p = doc.add_paragraph()
        for label, val in [
            ('参考人数：', stats['count']),
            ('缺考人数：', stats['missing']),
            ('最高分：', stats['max']),
            ('最低分：', stats['min']),
            ('平均分：', stats['avg']),
            ('中位数：', stats['median']),
            ('标准差：', stats['stdev']),
        ]:
            _run_font(p.add_run(f'{label}{val}　　'))
        _run_font(p.add_run(f'及格率：{stats["pass_rate"]}%'))

        dp = doc.add_paragraph('成绩分布：')
        for run in dp.runs:
            _run_font(run)

        dist_table = doc.add_table(rows=1 + len(stats['distribution']), cols=3, style='Table Grid')
        _set_cell(dist_table.cell(0, 0), '类别', bold=True)
        _set_cell(dist_table.cell(0, 1), '人数', bold=True)
        _set_cell(dist_table.cell(0, 2), '占比', bold=True)

        dist_idx = 1
        total = stats['count']
        for key, dist in stats['distribution'].items():
            _set_cell(dist_table.cell(dist_idx, 0), dist['label'])
            _set_cell(dist_table.cell(dist_idx, 1), str(dist['count']))
            pct = round(dist['count'] / total * 100, 1) if total else 0
            _set_cell(dist_table.cell(dist_idx, 2), f'{pct}%')
            dist_idx += 1


def export_module_4_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '四、课程评价结果')
    _render_module_4_to_docx(doc, report.report_data.get('module_4_evaluation_results', {}))
    return _to_buffer(doc)


# ── Module 5: Improvement Plan ──────────────────────────────────────────────

def export_module_5_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '五、课程持续改进方案及措施')

    data = report.report_data.get('module_5_improvement_plan', {})

    if isinstance(data, dict):
        # New structured format
        # 4.1
        _add_heading(doc, '4.1 连续两年课程评价结果系统地纳入课程持续改进的措施及其效果描述', level=2)
        _add_paragraph(doc, data.get('part1', ''))

        # 4.2
        _add_heading(doc, '4.2 本年度课程教学环节发现的问题、相应持续改进的措施以及描述预期将可能达到的效果', level=2)
        part2 = data.get('part2', {})
        if isinstance(part2, dict):
            _add_heading(doc, '(1) 存在的问题', level=3)
            _add_paragraph(doc, part2.get('problems', ''))
            _add_heading(doc, '(2) 持续改进措施', level=3)
            _add_paragraph(doc, part2.get('measures', ''))
            _add_heading(doc, '(3) 预期效果', level=3)
            _add_paragraph(doc, part2.get('expected_effects', ''))
        else:
            _add_paragraph(doc, str(part2))

        # 4.3
        _add_heading(doc, '4.3 其他可用的协助持续改进的资源', level=2)
        _add_paragraph(doc, data.get('part3', ''))
    else:
        # Legacy string format
        _add_paragraph(doc, str(data) if data else '待后续版本实现')

    return _to_buffer(doc)


def _render_module_5_to_docx(doc, data):
    """Render Module 5 structured data into an existing document (for merge)."""
    if isinstance(data, dict):
        _add_heading(doc, '4.1 连续两年课程评价结果系统地纳入课程持续改进的措施及其效果描述', level=2)
        _add_paragraph(doc, data.get('part1', ''))

        _add_heading(doc, '4.2 本年度课程教学环节发现的问题、相应持续改进的措施以及描述预期将可能达到的效果', level=2)
        part2 = data.get('part2', {})
        if isinstance(part2, dict):
            _add_heading(doc, '(1) 存在的问题', level=3)
            _add_paragraph(doc, part2.get('problems', ''))
            _add_heading(doc, '(2) 持续改进措施', level=3)
            _add_paragraph(doc, part2.get('measures', ''))
            _add_heading(doc, '(3) 预期效果', level=3)
            _add_paragraph(doc, part2.get('expected_effects', ''))
        else:
            _add_paragraph(doc, str(part2))

        _add_heading(doc, '4.3 其他可用的协助持续改进的资源', level=2)
        _add_paragraph(doc, data.get('part3', ''))
    else:
        _add_paragraph(doc, str(data) if data else '待后续版本实现')
