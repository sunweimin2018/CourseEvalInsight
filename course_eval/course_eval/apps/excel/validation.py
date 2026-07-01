import os
import re
from difflib import SequenceMatcher

from django.conf import settings

from .models import CourseFileRecord, WorkbookSnapshot
from .word_parser import parse_docx, extract_syllabus_fields
from .data_handler import get_effective_data


def _find_col(headers, keywords):
    """Find the first column header containing any of the given keywords."""
    for h in headers:
        clean = str(h).replace(' ', '').replace('　', '')
        for kw in keywords:
            if kw in clean:
                return h
    return None


def analyze_exam_status(user, course_id, class_id, semester_name):
    """Analyze exam status from the student_info table.

    Classifies students into three categories:
      - 正常考试 (normal):  是否缓考 ≠ 缓考 AND score > 0
      - 缓考 (deferred):    是否缓考 = 缓考 AND score is empty or 0
      - 缺考 (absent):      是否缓考 ≠ 缓考 AND score = 0

    Returns a dict with counts and detailed lists, or raises ValueError.
    """
    from .models import Semester

    semester = Semester.objects.filter(name=semester_name, user=user).first()
    if not semester:
        raise ValueError('学期不存在')

    student_info = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='student_info',
    ).first()
    if not student_info:
        raise ValueError('未找到学生基本信息表，请先上传')

    # ── Compare student_info metadata against syllabus ────────────────────
    student_meta = student_info.title_metadata or {}
    course_info = None
    syllabus = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type='syllabus',
    ).first()
    if syllabus:
        try:
            syllabus_path = os.path.join(settings.MEDIA_ROOT, syllabus.file_path)
            parsed = parse_docx(syllabus_path)
            fields = extract_syllabus_fields(
                parsed['paragraphs'], parsed['tables'],
                tables_rich=parsed.get('_tables_rich'),
                body_elements=parsed.get('_body_elements'),
            )
            course_info = _validate_course_info(student_meta, fields)
            course_info['student_info_has_metadata'] = course_info.pop('grades_has_metadata', False)
        except Exception:
            course_info = None

    data = get_effective_data(student_info, user.id)
    headers = data['headers']
    rows = data['rows']
    if not rows:
        raise ValueError('学生基本信息表为空')

    # Detect sub-header row (same logic as _analyze_student_info)
    first_row = rows[0]
    is_sub_header = any(
        any(label in str(v).replace(' ', '') for v in first_row.values())
        for label in ('学号', '姓名', '性别', '班级', '院系')
    )
    data_rows = rows[1:] if is_sub_header else rows
    effective_headers = list(first_row.keys())  # actual column keys

    # Build column mapping
    def _map_col(field_name):
        if is_sub_header:
            for col_key, cell_val in first_row.items():
                clean = str(cell_val).replace(' ', '').strip()
                if field_name in clean:
                    return col_key
        for h in headers:
            clean_h = str(h).replace(' ', '').strip()
            if field_name in clean_h:
                return h
        # Try first row values too
        for col_key, cell_val in first_row.items():
            clean = str(cell_val).replace(' ', '').strip()
            if field_name in clean:
                return col_key
        return None

    name_col = _map_col('姓名')
    sid_col = _map_col('学号')
    class_col = _map_col('班级')
    deferred_col = _map_col('是否缓考')

    # Find score column: any column with '成绩' or '分数' or '总评' or '期末' that is numeric
    score_col = None
    for h in effective_headers:
        clean = str(h).replace(' ', '').replace('　', '')
        if any(kw in clean for kw in ('成绩', '分数', '总评', '期末')):
            # Check if the column has numeric values
            sample = [r.get(h) for r in data_rows[:5] if r.get(h) is not None]
            numeric_count = sum(1 for v in sample if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().replace('.', '').replace('-', '').isdigit()))
            if numeric_count >= len(sample) * 0.6:
                score_col = h
                break

    result = {
        'has_deferred_col': deferred_col is not None,
        'has_score_col': score_col is not None,
        'total': len(data_rows),
        'course_info': course_info,
    }

    if not deferred_col and not score_col:
        # No exam status columns found — skip analysis, allow proceed
        result['skipped'] = True
        return result

    result['skipped'] = False

    def _cell(row, col, default=''):
        if col is None:
            return default
        v = row.get(col)
        if v is None:
            return default
        return str(v).strip()

    def _is_deferred(row):
        if not deferred_col:
            return False
        val = _cell(row, deferred_col)
        return '缓考' in val and '非缓考' not in val

    def _score_value(row):
        if not score_col:
            return None
        v = row.get(score_col)
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip()
        if s in ('', '-', 'None', 'nan'):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    normal = []
    deferred = []
    absent = []

    for r in data_rows:
        name = _cell(r, name_col)
        sid = _cell(r, sid_col)
        cls = _cell(r, class_col)
        is_def = _is_deferred(r)
        score = _score_value(r)

        info = {'name': name, 'student_id': sid, 'class_name': cls}
        if score is not None:
            info['score'] = score

        if is_def:
            deferred.append(info)
        elif score is not None and score > 0:
            normal.append(info)
        elif score is not None and score == 0:
            absent.append(info)
        elif score is None:
            # No score data — treat as normal if not deferred
            normal.append(info)

    result['normal'] = {'count': len(normal), 'students': normal}
    result['deferred'] = {'count': len(deferred), 'students': deferred}
    result['absent'] = {'count': len(absent), 'students': absent}
    result['score_col_name'] = score_col
    result['deferred_col_name'] = deferred_col

    return result


def extract_expected_items(evaluation_standards, fields=None):
    """Extract the expected evaluation item names with percentages.

    Prefers the new 'eval_items' field from extract_syllabus_fields if available.
    Falls back to legacy table parsing for backward compatibility.

    Returns a list of {name, percentage} dicts, or None.
    """
    # New path: use structured eval_items from _extract_evaluation_table
    if fields and isinstance(fields.get('eval_items'), list):
        items = [
            {'name': item['name'], 'percentage': item.get('percentage', '') or ''}
            for item in fields['eval_items'] if item.get('name')
        ]
        if items:
            return items

    # Legacy path for backward compatibility
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
            if len(grid) >= 3:
                for c, cell in enumerate(grid[1]):
                    if cell and '评价依据及成绩比例' in str(cell.get('text', '')):
                        weight_col_start = c
                        weight_col_end = c + cell.get('colspan', 1) - 1
                        break
            if weight_col_start is None:
                continue

        sub_row_idx = 1 if weight_col_start in [c for c, _ in enumerate(header_row)] else 2
        if sub_row_idx >= len(grid):
            continue

        items = []
        for c in range(weight_col_start, weight_col_end + 1):
            cell = grid[sub_row_idx][c] if c < len(grid[sub_row_idx]) else None
            if cell is None:
                continue
            text = str(cell.get('text', ''))
            text = text.replace('\n', '').replace('\r', '').strip()
            if text:
                items.append({'name': text, 'percentage': ''})

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

    expected_items is a list of {name, percentage} dicts.
    Returns a list of {expected, percentage, current, match, similarity?} dicts.
    Matching (greedy, per expected item):
      1. Exact match after normalize
      2. Fuzzy match via SequenceMatcher:
         - ratio >= 0.6: full match (match=True)
         - 0.3 <= ratio < 0.6: weak match (match=False, similarity=ratio)
         - ratio < 0.3: no match (column stays in pool)
    Matched columns are consumed (popped from remaining).
    Unmatched remaining columns are appended at the end as extra columns.
    """
    FULL_MATCH_THRESHOLD = 0.6
    WEAK_MATCH_THRESHOLD = 0.3

    comparisons = []

    def _norm(s):
        return re.sub(r'[（(][^）)]*[）)]', '', s).replace(' ', '').replace('　', '').strip()

    remaining = list(grade_columns)

    for item in expected_items:
        expected_name = item['name']
        best = None
        best_idx = None
        best_ratio = 0.0
        norm_e = _norm(expected_name)

        for i, col in enumerate(remaining):
            norm_c = _norm(col)
            if norm_e == norm_c:
                best = col
                best_idx = i
                best_ratio = 1.0
                break
            ratio = SequenceMatcher(None, norm_e, norm_c).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = col
                best_idx = i

        entry = {
            'expected': expected_name,
            'percentage': item.get('percentage', '') or '',
            'current': None,
            'match': False,
        }
        if best is not None and best_ratio >= FULL_MATCH_THRESHOLD:
            entry['current'] = best
            entry['match'] = True
            remaining.pop(best_idx)
        elif best is not None and best_ratio >= WEAK_MATCH_THRESHOLD:
            entry['current'] = best
            entry['match'] = False
            entry['similarity'] = round(best_ratio, 2)
            remaining.pop(best_idx)
        comparisons.append(entry)

    # Append unmatched remaining grade columns
    for col in remaining:
        comparisons.append({
            'expected': '',
            'percentage': '',
            'current': col,
            'match': False,
        })

    return comparisons


def _find_student_key(headers, rows):
    """Find the best column to use as a student identifier.

    Prefers '学号' if it holds data in most rows, otherwise uses '姓名'.
    Returns the column name, or None.
    """
    id_col = None
    name_col = None
    for h in headers:
        clean = str(h).replace(' ', '').replace('　', '')
        if not id_col and '学号' in clean:
            id_col = h
        if not name_col and '姓名' in clean:
            name_col = h

    if id_col:
        filled = sum(1 for r in rows if str(r.get(id_col, '')).strip() not in ('', 'None', 'nan'))
        if filled >= len(rows) * 0.5:
            return id_col
    return name_col or (headers[0] if headers else None)


def _compare_students(si_headers, si_rows, g_headers, g_rows):
    """Compare student lists between student_info and grades tables.

    Returns a dict with detailed comparison results, or None if identifiers
    can't be found.
    """
    si_key = _find_student_key(si_headers, si_rows)
    g_key = _find_student_key(g_headers, g_rows)

    if not si_key or not g_key:
        return None

    # Use the same logical field for comparison across both tables
    si_use_id = '学号' in str(si_key).replace(' ', '').replace('　', '')
    g_use_id = '学号' in str(g_key).replace(' ', '').replace('　', '')

    def _find_aux_col(headers, wanted):
        for h in headers:
            clean = str(h).replace(' ', '').replace('　', '')
            if wanted in clean:
                return h
        return None

    si_name_col = _find_aux_col(si_headers, '姓名') if si_use_id else si_key
    g_name_col = _find_aux_col(g_headers, '姓名') if g_use_id else g_key

    def _build_index(rows, key_col, name_col):
        idx = {}
        # Try to find a class column for richer comparison output
        class_col = _find_aux_col(list(rows[0].keys()) if rows else [], '班级')
        for r in rows:
            k = str(r.get(key_col, '')).strip()
            if not k or k == 'None':
                continue
            entry = {
                'name': str(r.get(name_col, '')).strip() if name_col else k,
                'student_id': k if key_col != name_col else '',
            }
            if class_col:
                cls = str(r.get(class_col, '')).strip()
                if cls and cls != 'None':
                    entry['class_name'] = cls
            idx[k] = entry
        return idx

    si_idx = _build_index(si_rows, si_key, si_name_col or si_key)
    g_idx = _build_index(g_rows, g_key, g_name_col or g_key)

    si_keys = set(si_idx.keys())
    g_keys = set(g_idx.keys())

    only_in_si = [si_idx[k] for k in sorted(si_keys - g_keys)]
    only_in_g = [g_idx[k] for k in sorted(g_keys - si_keys)]

    return {
        'matching_count': len(si_keys & g_keys),
        'only_in_student_info': only_in_si,
        'only_in_grades': only_in_g,
        'key_field': '学号' if (si_use_id or g_use_id) else '姓名',
    }


def _set_validation_status(user, course_id, class_id, semester, status):
    """Set validation_status on all three file types for a course/class/semester group."""
    CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user,
    ).update(validation_status=status)


def _set_file_validation_status(user, course_id, class_id, semester, file_type, status):
    """Set validation_status on a single file type for a course/class/semester group."""
    CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user=user, file_type=file_type,
    ).update(validation_status=status)


def _validate_course_info(grades_meta, syllabus_fields):
    """Compare course metadata from grades title row against syllabus fields.

    Only compares fields that are present in the grades metadata.
    Returns a dict with match status and per-field comparisons.
    """
    field_map = [
        ('course_code', 'course_code'),
        ('course_name', 'course_name'),
    ]

    comparisons = {}
    for meta_key, syllabus_key in field_map:
        gv = str(grades_meta.get(meta_key, '')).strip() if grades_meta.get(meta_key) else ''
        sv = str(syllabus_fields.get(syllabus_key, '')).strip()

        if gv and sv and sv != '未填写':
            norm_g = gv.replace(' ', '').replace('　', '')
            norm_s = sv.replace(' ', '').replace('　', '')
            match = norm_g == norm_s or SequenceMatcher(None, norm_g, norm_s).ratio() >= 0.6
        else:
            match = True  # Cannot compare when one side is missing

        comparisons[meta_key] = {
            'grades_value': gv,
            'syllabus_value': sv if sv != '未填写' else '',
            'match': match,
        }

    grades_has_metadata = any(
        str(grades_meta.get(k, '')).strip()
        for k in ('course_code', 'course_name')
    )

    all_match = all(c['match'] for c in comparisons.values())

    return {
        'match': all_match,
        'grades_has_metadata': grades_has_metadata,
        'comparisons': comparisons,
    }


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

    # ── 1. Student count / comparison ──────────────────────────────────────
    si_data = get_effective_data(student_info, user.id)
    g_data = get_effective_data(grades, user.id)

    si_count = si_data['total']
    g_count = g_data['total']
    count_match = (si_count == g_count)

    # Detailed student-by-student comparison
    student_comparison = _compare_students(
        si_data['headers'], si_data['rows'],
        g_data['headers'], g_data['rows'],
    )

    # One-to-one student ID match (not just count equality)
    student_id_match = (
        student_comparison is not None
        and student_comparison.get('matching_count', 0) == si_count == g_count
    )

    # ── 2. Header validation ──────────────────────────────────────────────
    syllabus_path = os.path.join(settings.MEDIA_ROOT, syllabus.file_path)
    parsed = parse_docx(syllabus_path)
    fields = extract_syllabus_fields(
        parsed['paragraphs'], parsed['tables'],
        tables_rich=parsed.get('_tables_rich'),
        body_elements=parsed.get('_body_elements'),
    )
    evaluation_standards = fields.get('evaluation_standards')

    expected_items = extract_expected_items(evaluation_standards, fields)
    if expected_items is None:
        # No recognizable weight table — skip header validation.
        # Student info was already validated during exam confirmation; only grades checks matter here.
        _set_file_validation_status(user, course_id, class_id, semester, 'syllabus', 'passed')
        _set_file_validation_status(user, course_id, class_id, semester, 'student_info', 'passed')
        _set_file_validation_status(user, course_id, class_id, semester, 'grades', 'pending')
        return {
            'student_count': {
                'match': count_match,
                'student_info_count': si_count,
                'grades_count': g_count,
                'comparison': student_comparison,
                'student_id_match': student_id_match,
            },
            'header_validation': None,
        }

    grade_headers = g_data['headers']
    name_idx = _find_name_col(grade_headers)
    total_idx = _find_total_col(grade_headers)

    if name_idx is None:
        _set_file_validation_status(user, course_id, class_id, semester, 'syllabus', 'passed')
        _set_file_validation_status(user, course_id, class_id, semester, 'student_info', 'passed')
        _set_file_validation_status(user, course_id, class_id, semester, 'grades', 'failed')
        return {
            'student_count': {
                'match': count_match,
                'student_info_count': si_count,
                'grades_count': g_count,
                'comparison': student_comparison,
                'student_id_match': student_id_match,
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
    # Also exclude 总评 column from matching
    end = total_idx if total_idx is not None else len(grade_headers)
    grade_eval_columns = [
        h for h in grade_headers[name_idx + 1:end]
        if '总评' not in str(h).replace(' ', '').replace('　', '')
    ]

    comparisons = _match_items(expected_items, grade_eval_columns)
    header_match = all(c['match'] for c in comparisons)

    # Student info already validated during exam confirmation phase.
    # Only header_match determines grades validation outcome.
    _set_file_validation_status(user, course_id, class_id, semester, 'syllabus', 'passed')
    _set_file_validation_status(user, course_id, class_id, semester, 'student_info', 'passed')
    _set_file_validation_status(user, course_id, class_id, semester, 'grades',
                                'pending' if header_match else 'failed')

    return {
        'student_count': {
            'match': count_match,
            'student_id_match': student_id_match,
            'student_info_count': si_count,
            'grades_count': g_count,
            'comparison': student_comparison,
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

    # Reset validation status on remaining files
    remaining = base_qs.exclude(file_type__in=types_deleted)
    if remaining.exists():
        _set_validation_status(user, course_id, class_id, semester, 'pending')

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

    # Reset validation status — user must re-validate after header changes
    _set_validation_status(
        grades_record.user, grades_record.course_id,
        grades_record.class_group_id, grades_record.semester,
        'pending',
    )
    return new_headers
