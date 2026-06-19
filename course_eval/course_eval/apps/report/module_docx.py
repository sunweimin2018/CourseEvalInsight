"""Single-module Word document export functions.

Each function takes a ReportRecord and returns a BytesIO buffer containing
a standalone .docx file for that module.
"""

from io import BytesIO
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


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

def export_module_4_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '四、课程评价结果')

    eval_results = report.report_data.get('module_4_evaluation_results', {})
    grade_analysis = eval_results.get('grade_analysis', {})

    if not grade_analysis:
        _add_paragraph(doc, '暂无成绩数据')
        return _to_buffer(doc)

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
        _set_cell(dist_table.cell(0, 0), '分数段', bold=True)
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

    return _to_buffer(doc)


# ── Module 5: Improvement Plan ──────────────────────────────────────────────

def export_module_5_docx(report):
    doc = _setup_document(report)
    _add_heading(doc, '五、课程持续改进方案及措施')
    _add_paragraph(doc, report.report_data.get('module_5_improvement_plan', '待后续版本实现'))
    return _to_buffer(doc)
