import os
import statistics

from django.conf import settings
from django.shortcuts import get_object_or_404

from course_eval.apps.excel.models import CourseFileRecord, Course, ClassGroup, Semester
from course_eval.apps.excel.word_parser import parse_docx, extract_syllabus_fields
from course_eval.apps.excel.data_handler import get_effective_data


SCORE_BUCKETS = [
    ('excellent', '优秀 (90-100)', 90, 101),
    ('good', '良好 (80-89)', 80, 90),
    ('medium', '中等 (70-79)', 70, 80),
    ('pass', '及格 (60-69)', 60, 70),
    ('fail', '不及格 (<60)', 0, 60),
]


def _find_file(course_id, class_id, semester, user_id, file_type):
    return CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester_id=semester.id, user_id=user_id, file_type=file_type,
    ).first()


NON_SCORE_COLUMNS = {'学号', '序号', '编号', 'ID', 'id', 'No', 'no', '学生证号'}

def _is_numeric_column(col_name, values):
    """Heuristic: a column is numeric if a majority of non-empty values parse as floats.
    Excludes identifier columns like 学号, 序号, 编号."""
    if col_name in NON_SCORE_COLUMNS:
        return False
    numeric_count = 0
    total_count = 0
    for v in values:
        if v is None or str(v).strip() == '' or str(v).strip() in ('缺考', '免修', '-', '/'):
            continue
        total_count += 1
        try:
            float(v)
            numeric_count += 1
        except (ValueError, TypeError):
            pass
    return total_count > 0 and numeric_count / total_count >= 0.8


def _parse_score(val):
    """Parse a score value; returns float or None for non-numeric / special marks."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ('', '缺考', '免修', '-', '/'):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _analyze_grades(headers, rows):
    """Compute statistics for each numeric score column."""
    score_columns = []
    for col in headers:
        col_values = [row.get(col) for row in rows if col in row]
        if _is_numeric_column(col, col_values):
            score_columns.append(col)

    analysis = {}
    for col in score_columns:
        raw = [_parse_score(row.get(col)) for row in rows]
        scores = [s for s in raw if s is not None]
        missing_count = len(raw) - len(scores)

        if not scores:
            continue

        dist = {}
        for key, label, lo, hi in SCORE_BUCKETS:
            dist[key] = {'label': label, 'count': sum(1 for s in scores if lo <= s < hi)}

        pass_count = sum(1 for s in scores if s >= 60)
        analysis[col] = {
            'count': len(scores),
            'missing': missing_count,
            'max': round(max(scores), 2),
            'min': round(min(scores), 2),
            'avg': round(statistics.mean(scores), 2),
            'median': round(statistics.median(scores), 2),
            'stdev': round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
            'pass_rate': round(pass_count / len(scores) * 100, 1) if scores else 0,
            'distribution': dist,
        }

    return analysis


def _analyze_student_info(headers, rows):
    """Extract student info statistics: total, gender, class distribution.

    Handles two-row header patterns where the first data row contains
    the actual column names (e.g. 学号, 姓名, 性别, 班级) while the
    parsed headers are generic \"Unnamed: N\".
    """
    if not rows:
        return {'total': 0, 'male': 0, 'female': 0, 'class_count': 0, 'classes': []}

    # Detect if the first row is a sub-header (contains known field labels)
    first_row = rows[0]
    is_sub_header = any(
        any(label in str(v).replace(' ', '') for v in first_row.values())
        for label in ('学号', '姓名', '性别', '班级', '院系')
    )

    data_rows = rows[1:] if is_sub_header else rows

    # Build a column mapping: normalized field name → column key
    col_map = {}
    if is_sub_header:
        for col_key, cell_val in first_row.items():
            clean = str(cell_val).replace(' ', '').strip()
            for field_name in ('学号', '姓名', '性别', '班级', '院系', '专业', '年级'):
                if field_name in clean:
                    col_map[field_name] = col_key
                    break
    else:
        # Try to find matching columns by checking header names directly
        for h in headers:
            clean_h = h.replace(' ', '').strip()
            for field_name in ('学号', '姓名', '性别', '班级', '院系', '专业', '年级'):
                if field_name in clean_h and field_name not in col_map:
                    col_map[field_name] = h
                    break
        # Also check first row if headers are generic
        for col_key, cell_val in first_row.items():
            clean = str(cell_val).replace(' ', '').strip()
            for field_name in ('学号', '姓名', '性别', '班级', '院系', '专业', '年级'):
                if field_name in clean and field_name not in col_map:
                    col_map[field_name] = col_key
                    break

    male_count = 0
    female_count = 0
    classes = set()

    gender_col = col_map.get('性别')
    class_col = col_map.get('班级')

    for row in data_rows:
        if gender_col:
            gender = str(row.get(gender_col, '')).replace(' ', '').strip()
            if gender == '男':
                male_count += 1
            elif gender == '女':
                female_count += 1

        if class_col:
            cls = str(row.get(class_col, '')).strip()
            if cls and cls != 'nan' and cls != 'None':
                classes.add(cls)

    return {
        'total': len(data_rows),
        'male': male_count,
        'female': female_count,
        'class_count': len(classes),
        'classes': sorted(classes),
    }


def generate_report(user_id, course_id, class_id, semester_name):
    """Orchestrate full report generation and return the report data dict."""

    course = get_object_or_404(Course, id=course_id, user_id=user_id)
    class_group = get_object_or_404(ClassGroup, id=class_id, user_id=user_id)
    semester, _ = Semester.objects.get_or_create(name=semester_name, user_id=user_id)

    syllabus_file = _find_file(course_id, class_id, semester, user_id, 'syllabus')
    student_info_file = _find_file(course_id, class_id, semester, user_id, 'student_info')
    grades_file = _find_file(course_id, class_id, semester, user_id, 'grades')

    # ── Module 1 & 2 & 3: Syllabus fields ──────────────────────────────────
    syllabus_fields = {}
    if syllabus_file:
        full_path = os.path.join(settings.MEDIA_ROOT, syllabus_file.file_path)
        parsed = parse_docx(full_path)
        syllabus_fields = extract_syllabus_fields(
            parsed['paragraphs'], parsed['tables'],
            tables_rich=parsed.get('_tables_rich'),
            body_elements=parsed.get('_body_elements'),
        )

    # ── Module 1 supplement: student info stats ────────────────────────────
    student_stats = {}
    if student_info_file:
        info_data = get_effective_data(student_info_file, user_id)
        student_stats = _analyze_student_info(info_data['headers'], info_data['rows'])

    # ── Module 4: Grade analysis ───────────────────────────────────────────
    grade_analysis = {}
    if grades_file:
        grades_data = get_effective_data(grades_file, user_id)
        grade_analysis = _analyze_grades(grades_data['headers'], grades_data['rows'])

    # Raw table key-value data for full fidelity (includes checkbox states)
    raw_table_kv = syllabus_fields.pop('_all_table_kv', {})

    # ── Assemble 5 modules ─────────────────────────────────────────────────
    report_data = {
        'module_1_course_info': {
            'course_name': syllabus_fields.get('course_name', course.name),
            'course_code': syllabus_fields.get('course_code', '未填写'),
            'teaching_class': syllabus_fields.get('teaching_class', class_group.name),
            'student_count': student_stats.get('total', '未填写'),
            'course_seq': syllabus_fields.get('course_seq', '未填写'),
            'total_hours': syllabus_fields.get('total_hours', '未填写'),
            'credits': syllabus_fields.get('credits', '未填写'),
            'textbook': syllabus_fields.get('textbook', '未填写'),
            'department': syllabus_fields.get('department', '未填写'),
            'teacher': syllabus_fields.get('teacher', '未填写'),
            'course_nature': syllabus_fields.get('course_nature', '未填写'),
            'course_type': syllabus_fields.get('course_type', '未填写'),
            # Extra statistics from student info
            'male_count': student_stats.get('male', 0),
            'female_count': student_stats.get('female', 0),
            'class_distribution': student_stats.get('classes', []),
            # Full raw table data (includes checkbox states for all fields)
            'raw_table_kv': raw_table_kv,
        },
        'module_2_objectives': syllabus_fields.get('course_objectives', '未填写'),
        'module_3_evaluation_standards': syllabus_fields.get('evaluation_standards', '未填写'),
        'module_4_evaluation_results': {
            'grade_analysis': grade_analysis,
            'score_columns': list(grade_analysis.keys()),
            'generated': bool(grade_analysis),
        },
        'module_5_improvement_plan': '待后续版本实现',
    }

    report_name = f'{course.name} {class_group.name} {semester.name} 成绩质量检测报告'

    return {
        'report_name': report_name,
        'report_data': report_data,
        'course': course,
        'class_group': class_group,
        'semester': semester,
        'syllabus_file': syllabus_file,
        'student_info_file': student_info_file,
        'grades_file': grades_file,
    }
