import os
from io import BytesIO

from django.conf import settings
from django.http import FileResponse

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

from .models import CourseFileRecord, Semester
from .word_parser import parse_docx, extract_syllabus_fields
from .data_handler import get_effective_data


THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'),
)
HEADER_FONT = Font(name='宋体', size=11, bold=True)
NORMAL_FONT = Font(name='宋体', size=11)
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _style(cell, font=NORMAL_FONT, alignment=CENTER):
    cell.font = font
    cell.alignment = alignment
    cell.border = THIN_BORDER


def _sc(ws, row, col, value, font=NORMAL_FONT, alignment=CENTER):
    c = ws.cell(row=row, column=col, value=value)
    _style(c, font, alignment)
    return c


def generate_grades_template(user, course_id, class_id, semester_name):
    """Generate a grades Excel template with headers from syllabus and data from student_info."""

    semester = Semester.objects.filter(name=semester_name, user=user).first()
    if not semester:
        raise ValueError('学期不存在')

    syllabus = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='syllabus',
    ).first()
    if not syllabus:
        raise ValueError('未找到课程大纲，请先上传')

    student_info = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='student_info',
    ).first()
    if not student_info:
        raise ValueError('未找到学生基本信息表，请先上传')

    # Parse syllabus to get course_obj_items
    syllabus_path = os.path.join(settings.MEDIA_ROOT, syllabus.file_path)
    parsed = parse_docx(syllabus_path)
    fields = extract_syllabus_fields(
        parsed['paragraphs'], parsed['tables'],
        tables_rich=parsed.get('_tables_rich'),
        body_elements=parsed.get('_body_elements'),
    )
    eval_items = fields.get('eval_items', [])
    eval_names = [item['name'] for item in eval_items if item.get('name')]

    # Get student data
    data = get_effective_data(student_info, user.id)
    rows = data['rows']
    headers = data['headers']

    # Build column mapping for 班级, 学号, 姓名
    def _find_col(keyword):
        for h in headers:
            clean = str(h).replace(' ', '').replace('　', '')
            if keyword in clean:
                return h
        return None

    class_col = _find_col('班级')
    sid_col = _find_col('学号')
    name_col = _find_col('姓名')

    # Build workbook
    wb = Workbook()
    ws = wb.active
    ws.title = '学生成绩表'

    # Header row
    fixed_headers = ['序号', '班级', '学号', '姓名']
    all_headers = fixed_headers + eval_names + ['总评']

    for c, h in enumerate(all_headers, 1):
        _sc(ws, 1, c, h, font=HEADER_FONT)

    # Data rows
    for r, student in enumerate(rows, 1):
        row_num = r + 1  # row 1 is header
        seq = r
        class_val = str(student.get(class_col, '')).strip() if class_col else ''
        sid_val = str(student.get(sid_col, '')).strip() if sid_col else ''
        name_val = str(student.get(name_col, '')).strip() if name_col else ''

        _sc(ws, row_num, 1, seq)
        _sc(ws, row_num, 2, class_val)
        _sc(ws, row_num, 3, sid_val)
        _sc(ws, row_num, 4, name_val)

        # Evaluation columns (empty for user to fill)
        for ci in range(len(eval_names)):
            _sc(ws, row_num, 5 + ci, '')

        # 总评 column (empty for user to fill)
        _sc(ws, row_num, 5 + len(eval_names), '')

    # Set column widths
    ws.column_dimensions['A'].width = 6   # 序号
    ws.column_dimensions['B'].width = 14  # 班级
    ws.column_dimensions['C'].width = 16  # 学号
    ws.column_dimensions['D'].width = 12  # 姓名
    for ci in range(len(eval_names)):
        col_letter = chr(ord('E') + ci) if ci < 22 else None
        if col_letter:
            ws.column_dimensions[col_letter].width = 22
    # 总评
    total_col = 5 + len(eval_names)
    col_letter = chr(ord('A') + total_col - 1) if total_col <= 26 else None
    if col_letter:
        ws.column_dimensions[col_letter].width = 10

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return FileResponse(
        buffer,
        filename='学生成绩表模板.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
    )
