import os
import re

from django.conf import settings

from .models import CourseFileRecord, WorkbookSnapshot
from .word_parser import parse_docx, extract_syllabus_fields
from .data_handler import get_effective_data


def extract_expected_items(evaluation_standards):
    """Extract the expected evaluation item names from the weight percentage table.

    Finds the table whose header contains '评价依据及成绩比例', then reads the
    cell texts in the row immediately below the spanned header cell.  Newlines
    inside cells are removed so multi-line headers become single-line.
    """
    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or len(grid) < 2:
            continue

        header_row = grid[0]
        weight_col_start = None
        weight_col_end = None

        for c, cell in enumerate(header_row):
            if cell and '评价依据及成绩比例' in str(cell.get('text', '')):
                weight_col_start = c
                weight_col_end = c + cell.get('colspan', 1) - 1
                break

        if weight_col_start is None:
            # Try row 1 as well (some tables have a two-level header)
            if len(grid) >= 3:
                for c, cell in enumerate(grid[1]):
                    if cell and '评价依据及成绩比例' in str(cell.get('text', '')):
                        weight_col_start = c
                        weight_col_end = c + cell.get('colspan', 1) - 1
                        break
            if weight_col_start is None:
                continue

        # Read the row below the weight header — the item-name sub-header row
        sub_row_idx = 1 if weight_col_start in [c for c, _ in enumerate(header_row)] else 2
        if sub_row_idx >= len(grid):
            continue

        items = []
        for c in range(weight_col_start, weight_col_end + 1):
            cell = grid[sub_row_idx][c] if c < len(grid[sub_row_idx]) else None
            if cell is None:
                continue
            text = str(cell.get('text', ''))
            # Remove newlines inside cells
            text = text.replace('\n', '').replace('\r', '').strip()
            if text:
                items.append(text)

        if items:
            return items

    return None


def _find_name_col(headers):
    """Locate the '姓名' column index in headers."""
    for i, h in enumerate(headers):
        cleaned = str(h).replace(' ', '').replace('　', '')
        if '姓名' in cleaned:
            return i
    return None


def _find_total_col(headers):
    """Locate a 'total' column after the name column.  Returns the first match."""
    total_keywords = ['合计', '总分', '总成绩', '总评']
    for i, h in enumerate(headers):
        cleaned = str(h).replace(' ', '').replace('　', '')
        for kw in total_keywords:
            if kw in cleaned:
                return i
    return None


def _match_items(expected_items, grade_columns):
    """Fuzzy-match expected evaluation items against grade column headers.

    Returns a list of {expected, current, match} dicts.  Matching:
      1. Exact match after normalize
      2. Substring containment
      3. Either side contains the other
    """
    comparisons = []

    def _norm(s):
        return re.sub(r'[（(][^）)]*[）)]', '', s).replace(' ', '').replace('　', '').strip()

    remaining = list(grade_columns)

    for expected in expected_items:
        best = None
        best_idx = None
        norm_e = _norm(expected)

        for i, col in enumerate(remaining):
            norm_c = _norm(col)
            if norm_e == norm_c:
                best = col
                best_idx = i
                break
            if norm_e in norm_c or norm_c in norm_e:
                if best is None:
                    best = col
                    best_idx = i

        if best is not None:
            comparisons.append({'expected': expected, 'current': best, 'match': True})
            remaining.pop(best_idx)
        else:
            comparisons.append({'expected': expected, 'current': None, 'match': False})

    return comparisons


def validate_grades_upload(user, course_id, class_id, semester_name):
    """Run all validations after a grades file has been uploaded.

    Returns a dict with student_count and header_validation results,
    or raises ValueError when prerequisites are missing.
    """
    from .models import Semester

    semester = Semester.objects.filter(name=semester_name, user=user).first()
    if not semester:
        raise ValueError('学期不存在')

    syllabus = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='syllabus',
    ).first()
    student_info = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='student_info',
    ).first()
    grades = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='grades',
    ).first()

    if not syllabus:
        raise ValueError('未找到课程大纲，请先上传')
    if not student_info:
        raise ValueError('未找到学生基本信息表，请先上传')
    if not grades:
        raise ValueError('未找到学生成绩表，请先上传')

    # ── 1. Student count ──────────────────────────────────────────────────
    si_data = get_effective_data(student_info, user.id)
    g_data = get_effective_data(grades, user.id)

    si_count = si_data['total']
    g_count = g_data['total']
    count_match = (si_count == g_count)

    # ── 2. Header validation ──────────────────────────────────────────────
    syllabus_path = os.path.join(settings.MEDIA_ROOT, syllabus.file_path)
    parsed = parse_docx(syllabus_path)
    fields = extract_syllabus_fields(
        parsed['paragraphs'], parsed['tables'],
        tables_rich=parsed.get('_tables_rich'),
        body_elements=parsed.get('_body_elements'),
    )
    evaluation_standards = fields.get('evaluation_standards')

    expected_items = extract_expected_items(evaluation_standards)
    if expected_items is None:
        # No recognizable weight table — skip header validation
        return {
            'student_count': {
                'match': count_match,
                'student_info_count': si_count,
                'grades_count': g_count,
            },
            'header_validation': None,
        }

    grade_headers = g_data['headers']
    name_idx = _find_name_col(grade_headers)
    total_idx = _find_total_col(grade_headers)

    if name_idx is None:
        return {
            'student_count': {
                'match': count_match,
                'student_info_count': si_count,
                'grades_count': g_count,
            },
            'header_validation': {
                'match': False,
                'expected_items': expected_items,
                'grade_columns': [],
                'comparisons': [],
                'error': '成绩表中未找到"姓名"列',
            },
        }

    # Columns between 姓名 (exclusive) and 合计 (exclusive, if present)
    end = total_idx if total_idx is not None else len(grade_headers)
    grade_eval_columns = grade_headers[name_idx + 1:end]

    comparisons = _match_items(expected_items, grade_eval_columns)
    header_match = all(c['match'] for c in comparisons)

    return {
        'student_count': {
            'match': count_match,
            'student_info_count': si_count,
            'grades_count': g_count,
        },
        'header_validation': {
            'match': header_match,
            'expected_items': expected_items,
            'grade_columns': grade_eval_columns,
            'comparisons': comparisons,
        },
    }


def resolve_count_mismatch(user, course_id, class_id, semester_name, choice):
    """Delete problematic files based on user's choice.

    choice = 'student_info_wrong' → delete student_info AND grades
    choice = 'grades_wrong'       → delete grades only
    """
    from .models import Semester

    semester = Semester.objects.filter(name=semester_name, user=user).first()
    if not semester:
        raise ValueError('学期不存在')

    base_qs = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user,
    )

    if choice == 'student_info_wrong':
        records = base_qs.filter(file_type__in=['student_info', 'grades'])
        types_deleted = ['student_info', 'grades']
    elif choice == 'grades_wrong':
        records = base_qs.filter(file_type='grades')
        types_deleted = ['grades']
    else:
        raise ValueError('无效的选择')

    for record in records:
        full_path = os.path.join(settings.MEDIA_ROOT, record.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        record.delete()

    return types_deleted


def fix_grades_headers(grades_record, user_id, header_mapping):
    """Update grade column headers and persist as a WorkbookSnapshot.

    header_mapping maps old column names to new column names.
    """
    data = get_effective_data(grades_record, user_id)
    old_headers = list(data['headers'])
    new_headers = [header_mapping.get(h, h) for h in old_headers]

    # Deactivate previous snapshots and create a new one
    WorkbookSnapshot.objects.filter(source_file=grades_record, is_latest=True).update(is_latest=False)
    WorkbookSnapshot.objects.create(
        source_file=grades_record,
        user_id=user_id,
        headers=new_headers,
        rows=data['rows'],
        row_count=data['total'],
        is_latest=True,
    )
    return new_headers
