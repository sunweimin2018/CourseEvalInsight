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


def _normalize_item_name(name):
    """Normalize an evaluation item name for fuzzy matching.

    Strips parenthetical content, common suffixes, and whitespace.
    """
    import re
    cleaned = re.sub(r'[（(][^）)]*[）)]', '', name)
    cleaned = re.sub(r'(成绩|得分|评分|考核|分数)$', '', cleaned)
    cleaned = cleaned.replace(' ', '').replace('　', '').strip()
    return cleaned


def _default_segments():
    """Return SCORE_BUCKETS in the same dict format as syllabus-derived segments."""
    return [{'label': label, 'lo': lo, 'hi': hi} for _, label, lo, hi in SCORE_BUCKETS]


def _parse_range_from_label(label):
    """Parse a numeric score range from a table header label.

    Examples: "90-100（优秀）" → (90, 101), "<60（不及格）" → (0, 60)
    Returns (lo, hi) where hi is exclusive, or None if no range found.
    """
    import re
    text = str(label).strip()
    # "NN-NN" pattern
    m = re.search(r'(\d+)\s*[-–—]\s*(\d+)', text)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2)) + 1  # exclusive upper bound
        return (lo, hi)
    # "<NN" pattern
    m = re.search(r'<\s*(\d+)', text)
    if m:
        return (0.0, float(m.group(1)))
    # ">NN" or ">=NN" pattern
    m = re.search(r'>[=]?\s*(\d+)', text)
    if m:
        return (float(m.group(1)), 101.0)
    return None


def _extract_score_segments_by_item(evaluation_standards):
    """Extract per-item score segment definitions from syllabus evaluation_standards.

    Scans ALL evaluation criteria tables. For each table:
      - Header row columns (excluding the item-name column) define score ranges.
      - Data row first-column text is the evaluation item name.

    Returns dict: {item_name: [{'label', 'lo', 'hi'}, ...]}
    or None if no usable evaluation criteria table is found.
    """
    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    result = {}

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or not grid[0]:
            continue

        header_row = grid[0]
        num_cols = len(header_row)
        if num_cols < 2:
            continue

        # Identify the item-name column (usually the one with "考核项目" / "考核内容")
        item_col_idx = None
        for c in range(num_cols):
            cell = header_row[c]
            if cell and ('考核项目' in str(cell.get('text', ''))
                         or '考核内容' in str(cell.get('text', ''))
                         or '评价项目' in str(cell.get('text', ''))):
                item_col_idx = c
                break

        # Extract segment definitions — skip the item column only if positively identified
        segments = []
        for c in range(num_cols):
            if item_col_idx is not None and c == item_col_idx:
                continue
            cell = header_row[c]
            if cell is None:
                continue
            text = str(cell.get('text', '')).strip()
            if not text:
                continue
            range_result = _parse_range_from_label(text)
            if range_result:
                lo, hi = range_result
                segments.append({'label': text, 'lo': lo, 'hi': hi})

        # Only treat as evaluation criteria table if we found 2+ segments
        if len(segments) < 2:
            continue

        # Read data rows: use the identified item column, or default to col 0
        read_item_col = item_col_idx if item_col_idx is not None else 0
        for r in range(1, len(grid)):
            row = grid[r]
            if read_item_col >= len(row):
                continue
            cell = row[read_item_col]
            if cell is None:
                continue  # merged cell covered by rowspan
            item_name = str(cell.get('text', '')).strip()
            if not item_name:
                continue
            result[item_name] = segments

    return result if result else None


def _extract_score_weights(evaluation_standards):
    """Extract evaluation item weight percentages from the syllabus weight table.

    Looks for a table whose header row contains "评价依据及成绩比例" and
    parses column headers like "课堂表现 10%" → {"课堂表现": 10.0}.

    Returns dict: {item_name: weight_pct, ...} or None if no weight table found.
    """
    import re

    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or len(grid) < 2:
            continue

        # Check if header row (row 0) contains "评价依据及成绩比例"
        header_row = grid[0]
        has_weight_header = False
        for cell in header_row:
            if cell and '评价依据及成绩比例' in str(cell.get('text', '')):
                has_weight_header = True
                break
        if not has_weight_header:
            continue

        # Column headers with percentages are typically in row 1 (due to merged cells in row 0)
        # Scan rows 0-1 for cells containing "item_name N%"
        result = {}
        pattern = re.compile(r'(.+?)\s*(\d+(?:\.\d+)?)\s*%')

        for row_idx in range(min(len(grid), 3)):
            row = grid[row_idx]
            for c in range(len(row)):
                cell = row[c]
                if cell is None:
                    continue
                text = str(cell.get('text', '')).strip()
                m = pattern.match(text)
                if m:
                    item_name = m.group(1).strip()
                    pct = float(m.group(2))
                    # Only keep the first occurrence of each item name
                    if item_name not in result and 0 < pct <= 100:
                        result[item_name] = pct

        if result:
            return result

    return None


def _match_score_weights(score_columns, item_weights_map):
    """Match score column names to weight percentages via fuzzy matching.

    Returns dict: {col_name: weight_pct, ...}
    Columns named '总评' are excluded.
    """
    if not item_weights_map:
        return {}

    result = {}
    for col in score_columns:
        norm_col = _normalize_item_name(col)
        if norm_col in ('总评', '总分'):
            continue

        # Level 1: exact match after normalization
        for item_name, pct in item_weights_map.items():
            if _normalize_item_name(item_name) == norm_col:
                result[col] = pct
                break
        if col in result:
            continue

        # Level 2: substring containment
        for item_name, pct in item_weights_map.items():
            norm_item = _normalize_item_name(item_name)
            if len(norm_item) >= 2 and (norm_item in norm_col or norm_col in norm_item):
                result[col] = pct
                break
        if col in result:
            continue

        # Level 3: character Jaccard similarity
        best_match = None
        best_score = 0.0
        col_chars = set(norm_col)
        for item_name, pct in item_weights_map.items():
            norm_item = _normalize_item_name(item_name)
            item_chars = set(norm_item)
            if not col_chars or not item_chars:
                continue
            jaccard = len(col_chars & item_chars) / len(col_chars | item_chars)
            if jaccard > 0.6 and jaccard > best_score:
                best_score = jaccard
                best_match = pct
        if best_match is not None:
            result[col] = best_match

    return result


def _normalize_scores_to_hundred(scores, weight_pct):
    """Detect score format and normalize to 百分制 (0-100 scale).

    Detection: if max(score) > weight_pct, scores are already in 百分制.
    Otherwise, they are weighted scores that need conversion.

    Returns (normalized_scores, is_weighted).
    """
    if not scores:
        return scores, False

    max_score = max(scores)
    if max_score > weight_pct + 1:
        # Already in 百分制 (e.g., 85 > 10)
        return scores, False
    else:
        # Weighted scores, convert to 百分制
        factor = 100.0 / weight_pct
        normalized = [round(s * factor, 2) for s in scores]
        return normalized, True


def _match_score_column(col_name, item_segments_map):
    """Find the best-matching item segments for a score column name.

    Three-level fuzzy matching:
      1. Exact match after normalization
      2. Substring containment (bidirectional)
      3. Character Jaccard similarity > 0.6

    Returns segments list or None.
    """
    if not item_segments_map:
        return None

    norm_col = _normalize_item_name(col_name)

    # Level 1: exact match after normalization
    for item_name, segments in item_segments_map.items():
        if _normalize_item_name(item_name) == norm_col:
            return segments

    # Level 2: substring containment
    for item_name, segments in item_segments_map.items():
        norm_item = _normalize_item_name(item_name)
        if len(norm_item) >= 2 and (norm_item in norm_col or norm_col in norm_item):
            return segments

    # Level 3: character Jaccard similarity
    best_match = None
    best_score = 0.0
    col_chars = set(norm_col)
    for item_name, segments in item_segments_map.items():
        norm_item = _normalize_item_name(item_name)
        item_chars = set(norm_item)
        if not col_chars or not item_chars:
            continue
        jaccard = len(col_chars & item_chars) / len(col_chars | item_chars)
        if jaccard > 0.6 and jaccard > best_score:
            best_score = jaccard
            best_match = segments

    return best_match


def _find_name_column_index(headers):
    """Find the positional index of the '姓名' column in headers list."""
    for i, h in enumerate(headers):
        clean = str(h).replace(' ', '').strip()
        if '姓名' in clean:
            return i
    return None


def _is_score_column(col_name, col_values, col_index, name_col_index):
    """Check if a column is a score column using position + content heuristics.

    Columns to the left of or at '姓名' are excluded.
    """
    if col_name in NON_SCORE_COLUMNS:
        return False
    if name_col_index is not None and col_index <= name_col_index:
        return False
    return _is_numeric_column(col_name, col_values)


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


def _parse_numeric(val, default=0.0):
    """Parse a value that might be a string with %, or a plain number."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace('%', '').replace('％', '').strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def _analyze_grades(headers, rows, segments_by_column=None, fallback_segments=None,
                    column_weights=None):
    """Compute statistics for each numeric score column.

    Args:
        segments_by_column: Optional dict mapping column name → segments list.
        fallback_segments: Optional segments list for unmatched columns.
        column_weights: Optional dict mapping column name → weight percentage.
            When a column has weight_pct and scores appear to be weighted
            (max ≤ weight_pct), they are normalized to 百分制 (0-100 scale).
    """
    name_col_index = _find_name_column_index(headers)
    score_columns = []
    for i, col in enumerate(headers):
        col_values = [row.get(col) for row in rows if col in row]
        if _is_score_column(col, col_values, i, name_col_index):
            score_columns.append(col)

    analysis = {}
    for col in score_columns:
        raw = [_parse_score(row.get(col)) for row in rows]
        scores = [s for s in raw if s is not None]
        missing_count = len(raw) - len(scores)

        if not scores:
            continue

        # Normalize scores to 百分制 if column has a weight
        is_weighted = False
        weight_pct = column_weights.get(col) if column_weights else None
        if weight_pct and weight_pct > 0:
            scores, is_weighted = _normalize_scores_to_hundred(scores, weight_pct)

        # Determine segments for this column
        col_segments = None
        if segments_by_column:
            col_segments = segments_by_column.get(col)
        if not col_segments:
            col_segments = fallback_segments
        if not col_segments:
            col_segments = _default_segments()

        dist = {}
        for seg in col_segments:
            count = sum(1 for s in scores if seg['lo'] <= s < seg['hi'])
            dist[seg['label']] = {'label': seg['label'], 'count': count}

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
            'is_weighted': is_weighted,
            'weight_pct': weight_pct,
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


def _parse_syllabus(syllabus_file):
    """Parse syllabus Word file and return extracted fields dict."""
    if not syllabus_file:
        return {}
    full_path = os.path.join(settings.MEDIA_ROOT, syllabus_file.file_path)
    parsed = parse_docx(full_path)
    return extract_syllabus_fields(
        parsed['paragraphs'], parsed['tables'],
        tables_rich=parsed.get('_tables_rich'),
        body_elements=parsed.get('_body_elements'),
    )


def _get_file_metadata(course_id, class_id, semester, user_id, file_type):
    """Get course metadata extracted from a file's title row."""
    from course_eval.apps.excel.models import CourseFileRecord
    record = CourseFileRecord.objects.filter(
        course_id=course_id, class_group_id=class_id,
        semester=semester, user_id=user_id, file_type=file_type,
    ).first()
    if record and record.title_metadata:
        return record.title_metadata
    return {}


# ── Per-module generation functions ────────────────────────────────────────

def generate_module_1(course, class_group, syllabus_fields, student_stats, raw_table_kv, grades_meta=None, student_info_meta=None):
    """Generate Module 1: Course Basic Information Table.

    Priority for course identity fields:
      1. grades_meta (from grades file title row — most reliable)
      2. syllabus_fields (from Word syllabus)
      3. course / class_group model names (fallback)
    """
    grades_meta = grades_meta or {}
    student_info_meta = student_info_meta or {}
    return {
        'course_name': grades_meta.get('course_name') or syllabus_fields.get('course_name', course.name),
        'course_code': syllabus_fields.get('course_code') or grades_meta.get('course_code', '未填写'),
        'teaching_class': '、'.join(student_stats.get('classes', [])) or syllabus_fields.get('teaching_class', class_group.name),
        'student_count': student_stats.get('total', '未填写'),
        'course_seq': student_info_meta.get('course_seq') or grades_meta.get('course_seq') or syllabus_fields.get('course_seq', '未填写'),
        'total_hours': syllabus_fields.get('total_hours', '未填写'),
        'credits': syllabus_fields.get('credits', '未填写'),
        'textbook': syllabus_fields.get('textbook', '未填写'),
        'department': syllabus_fields.get('department', '未填写'),
        'teacher': syllabus_fields.get('teacher', '未填写'),
        'course_nature': syllabus_fields.get('course_nature', '未填写'),
        'course_type': syllabus_fields.get('course_type', '未填写'),
        'male_count': student_stats.get('male', 0),
        'female_count': student_stats.get('female', 0),
        'class_distribution': student_stats.get('classes', []),
        'raw_table_kv': raw_table_kv,
    }


def generate_module_2(syllabus_fields):
    """Generate Module 2: Course Objectives."""
    return syllabus_fields.get('course_objectives', '未填写')


def generate_module_3(syllabus_fields):
    """Generate Module 3: Evaluation Standards."""
    return syllabus_fields.get('evaluation_standards', '未填写')


def _build_grade_summary_prompt(section):
    """Build a prompt for AI to generate a ~400-word grade analysis summary."""
    s = section['stats']
    segs = section['segments']
    col = section['col_name']

    dist_lines = '\n'.join(
        f"- {seg['label']}: {seg['count']}人，占比{seg['pct']}%"
        for seg in segs
    )

    return f"""请以教育数据分析师的身份，对以下"{col}"的成绩统计数据写一段约400字的分析文字描述：

【成绩统计数据】
- 参考人数：{s['count']}人
- 缺考人数：{s['missing']}人
- 最高分：{s['max']}分
- 最低分：{s['min']}分
- 平均分：{s['avg']}分
- 中位数：{s['median']}分
- 标准差：{s['stdev']}
- 及格率：{s['pass_rate']}%

【成绩分布】
{dist_lines}

请从以下几个角度进行分析：
1. 整体成绩水平如何？
2. 成绩分布的集中与离散程度
3. 需要关注的问题（如不及格比例、高分比例等）
4. 简要的教学改进建议

要求：语言专业、客观，控制在400字左右，不要分段标题，直接以连贯段落输出。"""


def _generate_ai_summary(section):
    """Call Zhipu AI API to generate an AI summary for a grade section."""
    from course_eval.utils.zhipu import call_zhipu

    system_prompt = '你是一位经验丰富的教育数据分析师，擅长对课程成绩数据进行专业、客观的分析。'
    user_prompt = _build_grade_summary_prompt(section)

    try:
        result = call_zhipu(system_prompt, user_prompt)
        return result
    except Exception:
        return ''


def generate_module_4(grades_file, user_id, evaluation_standards=None):
    """Generate Module 4: Evaluation Results (grade analysis).

    Each score column is matched against evaluation criteria tables from the
    syllabus so that different columns can use different score-segment labels
    (e.g. "优秀/良好/中等/合格/不合格" for 课堂表现 vs "A/B/C/D/F" for 作业).

    Args:
        evaluation_standards: Optional list of blocks from syllabus parsing.
    """
    if not grades_file:
        return {
            'sections': [],
            'segment_labels': [],
            'generated': False,
            'fallback': True,
            'grade_analysis': {},
            'score_columns': [],
        }

    grades_data = get_effective_data(grades_file, user_id)

    # Extract per-item segment definitions from syllabus evaluation tables
    item_segments_map = _extract_score_segments_by_item(evaluation_standards)
    fallback = item_segments_map is None

    # Determine fallback segments (first table's segments, or SCORE_BUCKETS)
    if item_segments_map:
        fallback_segments = next(iter(item_segments_map.values()), None)
    else:
        fallback_segments = None

    # Extract column weight percentages from syllabus
    item_weights_map = _extract_score_weights(evaluation_standards)

    # Match each score column to its corresponding evaluation item
    segments_by_column = {}
    if item_segments_map:
        headers = grades_data['headers']
        rows = grades_data['rows']
        name_col_index = _find_name_column_index(headers)
        score_columns = []
        for i, col in enumerate(headers):
            col_values = [row.get(col) for row in rows if col in row]
            if _is_score_column(col, col_values, i, name_col_index):
                score_columns.append(col)
                matched = _match_score_column(col, item_segments_map)
                if matched is not None:
                    segments_by_column[col] = matched
    else:
        headers = grades_data['headers']
        rows = grades_data['rows']
        name_col_index = _find_name_column_index(headers)
        score_columns = []
        for i, col in enumerate(headers):
            col_values = [row.get(col) for row in rows if col in row]
            if _is_score_column(col, col_values, i, name_col_index):
                score_columns.append(col)

    # Match score columns to their weight percentages
    column_weights = _match_score_weights(score_columns, item_weights_map) if item_weights_map else {}

    grade_analysis = _analyze_grades(
        grades_data['headers'], grades_data['rows'],
        segments_by_column=segments_by_column if segments_by_column else None,
        fallback_segments=fallback_segments,
        column_weights=column_weights if column_weights else None,
    )

    # Build segment_labels as the union of all labels used across all columns
    all_labels = set()
    for stats in grade_analysis.values():
        for dist in stats['distribution'].values():
            all_labels.add(dist['label'])

    # Build new sections format (without AI summaries first)
    sections = []
    future_tasks = []

    for col_name, stats in grade_analysis.items():
        # Build description with weight info if available
        weight_pct = stats.get('weight_pct')
        if weight_pct:
            desc1 = f'学生{col_name}成绩统计（占总评{weight_pct:.0f}%）'
        else:
            desc1 = f'学生{col_name}成绩统计'
        desc2 = f'学生课程{col_name}成绩分布如下表所示'

        section_segments = []
        total = stats['count']
        for key, dist in stats['distribution'].items():
            pct = round(dist['count'] / total * 100, 1) if total else 0
            section_segments.append({
                'label': dist['label'],
                'count': dist['count'],
                'pct': pct,
            })

        # Determine segment source for UI display
        if segments_by_column and col_name in segments_by_column:
            segment_source = 'matched'
        elif fallback_segments:
            segment_source = 'fallback'
        else:
            segment_source = 'default'

        section_data = {
            'col_name': col_name,
            'description_line_1': desc1,
            'description_line_2': desc2,
            'stats': {
                'count': stats['count'],
                'missing': stats['missing'],
                'max': stats['max'],
                'min': stats['min'],
                'avg': stats['avg'],
                'median': stats['median'],
                'stdev': stats['stdev'],
                'pass_rate': stats['pass_rate'],
            },
            'segments': section_segments,
            'avg_score': stats['avg'],
            'ai_summary': '',
            'segment_source': segment_source,
            'weight_pct': weight_pct,
            'is_weighted': stats.get('is_weighted', False),
        }
        sections.append(section_data)
        future_tasks.append((len(sections) - 1, section_data))

    # Generate AI summaries in parallel (best-effort, non-blocking)
    if future_tasks:
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
        executor = ThreadPoolExecutor(max_workers=min(len(future_tasks), 4))
        try:
            futures = {
                executor.submit(_generate_ai_summary, task[1]): task[0]
                for task in future_tasks
            }
            for future in as_completed(futures, timeout=70):
                idx = futures[future]
                try:
                    sections[idx]['ai_summary'] = future.result()
                except Exception:
                    pass
        except TimeoutError:
            pass
        finally:
            executor.shutdown(wait=False)

    return {
        'sections': sections,
        'segment_labels': sorted(all_labels) if all_labels else [],
        'generated': bool(grade_analysis),
        'fallback': fallback,
        'grade_analysis': grade_analysis,
        'score_columns': list(grade_analysis.keys()),
    }


def _build_module6_context(course_name, objectives, module_4):
    """Build a context dict for Module 6 AI generation from Modules 1/2/4 data."""
    grade_lines = []
    if module_4 and module_4.get('sections'):
        for sec in module_4['sections']:
            s = sec['stats']
            grade_lines.append(
                f"{sec['col_name']}：参考{s['count']}人，平均{s['avg']}分，"
                f"最高{s['max']}分，最低{s['min']}分，及格率{s['pass_rate']}%"
            )
    grade_summary = '\n'.join(grade_lines) if grade_lines else '暂无成绩数据'

    return {
        'course_name': course_name,
        'objectives': objectives if objectives else '未填写',
        'grade_summary': grade_summary,
    }


def _build_module6_prompt(context):
    """Build a prompt for AI to generate Module 5 continuous improvement plan."""
    course_name = context.get('course_name', '')
    objectives = context.get('objectives', '')
    grade_summary = context.get('grade_summary', '')

    return f"""你是一位经验丰富的大学教学督导专家。请根据以下课程信息，为该课程撰写"课程持续改进方案及措施"。

【课程名称】
{course_name}

【课程目标】
{objectives}

【成绩概况】
{grade_summary}

请严格按照以下格式输出，使用【第1部分】【第2部分】【第3部分】作为每部分开始的标记（这三个标记必须原样出现在输出中，不可省略）：

【第1部分】
连续两年课程评价结果系统地纳入课程持续改进的措施及其效果描述。
要求：基于成绩概况，描述近两年该课程的持续改进情况。如果只有当年数据，则基于现有数据合理推测趋势。约200-300字。

【第2部分】
本年度课程教学环节发现的问题、相应持续改进的措施以及描述预期将可能达到的效果。
本部分必须包含以下三个子标题（必须原样输出，不可省略）：
(1)存在的问题
分析当前教学中存在的3-5个具体问题，要具体、有针对性。每个问题以"第一，""第二，"开头。
(2)持续改进措施
针对上述问题逐条提出改进措施，每条措施要具体可操作。每条以"第一，""第二，"开头。
(3)预期效果
针对改进措施，描述预期可能达到的效果。每条以"第一，""第二，"开头。
约400-600字。

【第3部分】
其他可用的协助持续改进的资源。
要求：列出2-4项可用的协助资源（如教材微课、网络学习视频、实验平台、助教辅导、学习小组等），约80-150字。

要求：语言专业、客观、具体，基于课程实际数据进行分析和建议，避免空话套话。"""


def _parse_module6_response(text):
    """Parse Zhipu response into structured Module 5 data.

    Uses 【第N部分】 markers to split the three major sections,
    then parses (1)/(2)/(3) sub-headings within part 2.
    Falls back to a reasonable structure if parsing fails.
    """
    import re

    def _extract_between(text, start_marker, end_marker=None):
        """Extract text between two markers. If end_marker is None, extract to end."""
        start = text.find(start_marker)
        if start == -1:
            return ''
        start += len(start_marker)
        if end_marker:
            end = text.find(end_marker, start)
            if end == -1:
                return text[start:].strip()
            return text[start:end].strip()
        return text[start:].strip()

    # Extract three parts using 【第N部分】 markers
    part1 = _extract_between(text, '【第1部分】', '【第2部分】')
    part2_text = _extract_between(text, '【第2部分】', '【第3部分】')
    part3 = _extract_between(text, '【第3部分】')

    # If markers not found, fall back to --- split
    if not part1 and not part2_text and not part3:
        parts = text.split('---')
        if len(parts) >= 1:
            part1 = parts[0].strip()
        if len(parts) >= 2:
            part2_text = parts[1].strip()
        if len(parts) >= 3:
            part3 = parts[2].strip()

    # Parse part2 sub-sections using (1)/(2)/(3) markers
    problems = ''
    measures = ''
    expected_effects = ''

    # Try extracting between sub-section markers
    problems = _extract_between(part2_text, '(1)存在的问题', '(2)持续改进措施')
    if not problems:
        problems = _extract_between(part2_text, '（1）存在的问题', '（2）持续改进措施')

    measures = _extract_between(part2_text, '(2)持续改进措施', '(3)预期效果')
    if not measures:
        measures = _extract_between(part2_text, '（2）持续改进措施', '（3）预期效果')

    expected_effects = _extract_between(part2_text, '(3)预期效果')
    if not expected_effects:
        expected_effects = _extract_between(part2_text, '（3）预期效果')

    # Fallback: if sub-section extraction failed, try reading line by line
    if not problems and not measures and not expected_effects:
        current_section = None
        for line in part2_text.split('\n'):
            stripped = line.strip()
            if '(1)' in stripped and '问题' in stripped:
                current_section = 'problems'
                continue
            elif '(2)' in stripped and '措施' in stripped:
                current_section = 'measures'
                continue
            elif '(3)' in stripped and '效果' in stripped:
                current_section = 'effects'
                continue

            if current_section == 'problems':
                problems += line + '\n'
            elif current_section == 'measures':
                measures += line + '\n'
            elif current_section == 'effects':
                expected_effects += line + '\n'

    return {
        'part1': part1.strip(),
        'part2': {
            'problems': problems.strip(),
            'measures': measures.strip(),
            'expected_effects': expected_effects.strip(),
        },
        'part3': part3.strip(),
    }


def _get_fallback_module6():
    """Structured fallback template when AI generation fails."""
    return {
        'part1': (
            '本课程在上一轮教学评估后，针对学生反馈和实践教学需要，'
            '对教学内容和方法进行了持续改进。通过优化课程设计、加强实践环节、'
            '完善考核方式等措施，逐步提升了教学质量。本轮评估结果反映了这些改进的初步成效，'
            '也为下一步优化提供了数据支撑。'
        ),
        'part2': {
            'problems': (
                '第一，学生对基本概念理解不够清晰和深入，需要在上机操作过程中进一步加强，'
                '同时应倡导学生在不使用AI的情况下，尽量能独立完成相关操作练习。\n'
                '第二，学生过度依赖实验指导说明，独立思考能力较弱。\n'
                '第三，学生能根据各章节刻板地去完成编程，碰到综合性题目就无从下手。\n'
                '第四，综合性编程题目的讲解和练习不足，需要在课程安排中增加相应课时。'
            ),
            'measures': (
                '第一，对基本概念加强课堂提问及课后练习，倡导学生在不使用AI的情况下，'
                '尽量能独立完成相关操作练习。\n'
                '第二，通过建立学习小组的方式，利用课后时间互相讨论，更好地帮助学生'
                '提高学习兴趣和主动性，提升独立思考能力。\n'
                '第三，继续加大程序设计基本思想的讲解，结合基础概念用综合性的应用'
                '去强化学生对基本概念理解和综合知识的应用。针对不同专业背景的学生，'
                '授课时着重对基本概念的理解以及知识的灵活应用能力，而非死记硬背，'
                '从而提高对课程不太感兴趣的同学的积极性，克服畏难思想。\n'
                '第四，加大对综合性题目的讲解和练习，在课程安排中多一些课时量，'
                '有针对性地对综合性内容进行细致的讲解，以增强学生的综合应用能力。'
            ),
            'expected_effects': (
                '第一，学生对基本概念的掌握更加清晰和深入。\n'
                '第二，学生独立思考能力得到提高。\n'
                '第三，学生在实践中能独立完成一些综合性的应用。'
            ),
        },
        'part3': '布置线下作业，利用教材微课及网络学习视频等资源加强综合能力的训练。',
    }


def _parse_objective_item_mapping(evaluation_standards):
    """Parse objective-to-evaluation-item mapping from syllabus evaluation tables.

    Looks for tables whose first column header contains '课程目标' and which
    have columns for '评价内容'/'考核项目', '目标分值', '权重' etc.

    Returns list of dicts: [{'objective': str, 'item': str, 'target_score': float,
                              'weight_pct': float}, ...]
    or None if no mapping table found.
    """
    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or len(grid) < 2:
            continue

        header = grid[0]
        num_cols = len(header)

        # Identify columns by header text
        obj_col = None
        item_col = None
        score_col = None
        weight_col = None
        for c in range(num_cols):
            cell = header[c]
            if cell is None:
                continue
            text = str(cell.get('text', '')).replace(' ', '').strip()
            if '课程目标' in text and '达成' not in text:
                obj_col = c
            elif '评价' in text or '考核' in text or '项目' in text:
                item_col = c
            elif '目标分值' in text or '分值' in text:
                score_col = c
            elif '权重' in text or '比例' in text or '系数' in text:
                weight_col = c

        # Need at least objective and item columns
        if obj_col is None or item_col is None:
            continue

        result = []
        for r in range(1, len(grid)):
            row = grid[r]
            if obj_col >= len(row) or item_col >= len(row):
                continue

            obj_cell = row[obj_col]
            item_cell = row[item_col]
            if obj_cell is None or item_cell is None:
                continue

            objective = str(obj_cell.get('text', '')).strip()
            item = str(item_cell.get('text', '')).strip()
            if not objective or not item:
                continue

            target_score = None
            if score_col is not None and score_col < len(row) and row[score_col]:
                try:
                    target_score = float(str(row[score_col].get('text', '')).strip())
                except ValueError:
                    pass

            weight_pct = None
            if weight_col is not None and weight_col < len(row) and row[weight_col]:
                import re
                wt_text = str(row[weight_col].get('text', '')).strip()
                m = re.search(r'(\d+(?:\.\d+)?)\s*%', wt_text)
                if m:
                    weight_pct = float(m.group(1))
                else:
                    try:
                        weight_pct = float(wt_text)
                    except ValueError:
                        pass

            result.append({
                'objective': objective,
                'item': item,
                'target_score': target_score,
                'weight_pct': weight_pct,
            })

        if result:
            return result

    return None


def _clean_eval_item_name(name):
    """Remove trailing percentage suffix from evaluation item column headers.

    e.g. "课堂表现 10%" → "课堂表现", "上机实验30%" → "上机实验"
    """
    import re
    return re.sub(r'\s*\d+%$', '', name).strip()


def _parse_wide_eval_table(evaluation_standards):
    """Parse wide-format evaluation standards table from syllabus.

    Locates the first table whose header column contains '课程目标' (the
    "考核环节构成及成绩比例" table) and extracts:
      - evaluation item names (cleaned column headers)
      - weight percentages per objective×item (intersection cell values)
      - overall achievement rate per objective (成绩比例 column total)

    Handles two table layouts:
      Simple:  Row 0 cols 1+ = evaluation item names, data starts at Row 1
      Two-level: Row 0 has a spanning header (e.g. "评价依据及成绩比例(%)"),
                 Row 1 has the actual item names, data starts at Row 2

    Returns list of dicts:
        [{objective, items: [{item, weight_pct}, ...], achievement_rate}, ...]
    or None if no suitable table found.
    """
    import re

    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    spanning_keywords = ['评价依据', '考核方式', '评价方式', '考核依据']
    total_keywords = ['成绩比例', '比例', '合计']

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or len(grid) < 2:
            continue

        row0 = grid[0]
        num_cols = len(row0)

        # ── Locate the "课程目标" column ──
        course_obj_col = None
        for c in range(min(3, num_cols)):
            cell = row0[c]
            if cell is None:
                continue
            text = str(cell.get('text', '')).replace(' ', '').strip()
            if '课程目标' in text:
                course_obj_col = c
                break

        if course_obj_col is None:
            continue

        # ── Determine header layout (simple vs two-level) ──
        is_two_level = False
        span_start = None   # first col index covered by the spanning header
        span_end = None     # exclusive end (span_start + colspan)

        # Check 1: colspan
        for c in range(course_obj_col + 1, num_cols):
            cell = row0[c]
            if cell is None:
                continue
            if cell.get('colspan', 1) > 1:
                is_two_level = True
                span_start = c
                span_end = c + cell['colspan']
                break

        # Check 2: spanning keywords in text + colspan>1
        if not is_two_level:
            for c in range(course_obj_col + 1, num_cols):
                cell = row0[c]
                if cell is None:
                    continue
                cs = cell.get('colspan', 1)
                text = str(cell.get('text', '')).replace(' ', '').strip()
                if any(kw in text for kw in spanning_keywords) and cs > 1:
                    is_two_level = True
                    span_start = c
                    span_end = c + cs
                    break

        # Check 3: Row 1 structural hints
        if not is_two_level and len(grid) >= 3:
            row1 = grid[1]
            if len(row1) > course_obj_col:
                r1c = row1[course_obj_col]
                if r1c is None or str(r1c.get('text', '')).strip() == '课程目标':
                    is_two_level = True
                    span_start = course_obj_col + 1
                    span_end = num_cols

        if is_two_level and len(grid) >= 3:
            sub_header_row = grid[1]
            data_start = 2

            # Build eval column map: {col_index: clean_item_name}
            eval_cols = {}   # col_index → clean_name
            total_col = None

            for c in range(course_obj_col + 1, num_cols):
                if c >= len(sub_header_row):
                    continue
                cell = sub_header_row[c]
                cell_text = str(cell.get('text', '')).strip() if cell else ''

                in_span = (span_start is not None and span_start <= c < span_end)

                if in_span and cell_text:
                    eval_cols[c] = _clean_eval_item_name(cell_text)
                elif not in_span:
                    # Check if this is a total / 成绩比例 column
                    row0_cell = row0[c] if c < len(row0) else None
                    row0_text = str(row0_cell.get('text', '')).strip() if row0_cell else ''
                    if any(kw in row0_text for kw in total_keywords):
                        total_col = c
                    elif not cell_text and row0_text:
                        # sub-header empty but main header has content
                        total_col = c
        else:
            # Simple: Row 0 cols after course_obj_col are the item names
            item_names = {}
            total_col = None
            for c in range(course_obj_col + 1, num_cols):
                cell = row0[c]
                if cell is None:
                    continue
                text = str(cell.get('text', '')).strip()
                if not text:
                    continue
                if any(kw in text for kw in total_keywords):
                    total_col = c
                else:
                    item_names[c] = _clean_eval_item_name(text)

            eval_cols = item_names
            data_start = 1

        if not eval_cols:
            continue

        # ── Parse data rows ──
        result = []
        for r in range(data_start, len(grid)):
            row = grid[r]
            if not row or len(row) == 0:
                continue

            obj_cell = row[course_obj_col]
            if obj_cell is None:
                continue
            objective = str(obj_cell.get('text', '')).strip()
            if not objective:
                continue
            if objective == '课程目标':
                continue
            if '合计' in objective:
                continue

            items = []
            for col_idx, item_name in eval_cols.items():
                if col_idx >= len(row):
                    continue
                cell = row[col_idx]
                if cell is None:
                    continue
                cell_text = str(cell.get('text', '')).strip()
                if cell_text:
                    items.append({
                        'item': item_name,
                        'weight_pct': cell_text,
                    })

            # Extract achievement_rate from total column
            achievement_rate = '0%'
            if total_col is not None and total_col < len(row):
                total_cell = row[total_col]
                if total_cell is not None:
                    total_text = str(total_cell.get('text', '')).strip()
                    if total_text:
                        achievement_rate = total_text

            if items:
                result.append({
                    'objective': objective,
                    'items': items,
                    'achievement_rate': achievement_rate,
                })

        if result:
            return result

    return None


def _parse_eval_item_totals(evaluation_standards):
    """Extract the 合计 (total) row values from the wide-format evaluation table.

    Returns a dict mapping clean item name → numeric total value,
    e.g. {'课堂表现': 10, '课后作业': 20, '上机实验': 30, '期末考试': 40}
    Returns None if the 合计 row cannot be found.
    """
    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

    for block in evaluation_standards:
        if block.get('type') != 'table':
            continue
        grid = block.get('grid')
        if not grid or len(grid) < 3:
            continue

        # Find the 合计 row and the column headers
        row0 = grid[0]
        num_cols = len(row0)
        course_obj_col = None
        for c in range(min(3, num_cols)):
            cell = row0[c]
            if cell is None:
                continue
            if '课程目标' in str(cell.get('text', '')).replace(' ', '').strip():
                course_obj_col = c
                break
        if course_obj_col is None:
            continue

        # Determine eval item columns (same logic as _parse_wide_eval_table)
        is_two_level = False
        span_start, span_end = None, None
        for c in range(course_obj_col + 1, num_cols):
            cell = row0[c]
            if cell is None:
                continue
            if cell.get('colspan', 1) > 1:
                is_two_level = True
                span_start = c
                span_end = c + cell['colspan']
                break

        if not is_two_level and len(grid) >= 3:
            row1 = grid[1]
            if len(row1) > course_obj_col and row1[course_obj_col] is None:
                is_two_level = True
                span_start = course_obj_col + 1
                span_end = num_cols

        # Build eval_cols map
        eval_cols = {}
        if is_two_level:
            sub_header_row = grid[1]
            for c in range(course_obj_col + 1, num_cols):
                if c >= len(sub_header_row):
                    continue
                cell = sub_header_row[c]
                text = str(cell.get('text', '')).strip() if cell else ''
                if span_start is not None and span_start <= c < span_end and text:
                    eval_cols[c] = _clean_eval_item_name(text)
        else:
            for c in range(course_obj_col + 1, num_cols):
                cell = row0[c]
                if cell is None:
                    continue
                text = str(cell.get('text', '')).strip()
                if text and '合计' not in text and '比例' not in text:
                    eval_cols[c] = _clean_eval_item_name(text)

        if not eval_cols:
            continue

        # Find the 合计 row — check any cell whose text contains '合计'
        for r in range(1, len(grid)):
            row = grid[r]
            if not row:
                continue
            is_total_row = False
            for c in range(min(3, len(row))):
                cell = row[c]
                if cell is not None and '合计' in str(cell.get('text', '')):
                    is_total_row = True
                    break
            if is_total_row:
                totals = {}
                for col_idx, item_name in eval_cols.items():
                    if col_idx < len(row) and row[col_idx] is not None:
                        val_text = str(row[col_idx].get('text', '')).strip()
                        totals[item_name] = _parse_weight_pct_to_target(val_text)
                return totals if totals else None

    return None


def _parse_weight_pct_to_target(weight_pct):
    """Convert a weight_pct value to a target_score numeric value.

    '4%' → 4.0,  '26%' → 26.0,  0.04 → 4.0,  None → 0
    """
    if weight_pct is None:
        return 0
    if isinstance(weight_pct, (int, float)):
        return round(weight_pct * 100, 1) if weight_pct < 1 else float(weight_pct)
    s = str(weight_pct).strip().replace('%', '').strip()
    try:
        val = float(s)
        return round(val * 100, 1) if val < 1 else val
    except (ValueError, TypeError):
        return 0


def _generate_section_5_1(evaluation_standards, semester_name=''):
    """Generate section 5.1 data: 课程目标达成情况 summary table.

    Extracts objective-to-item mapping from evaluation standards tables
    (supporting both long-format and wide-format) and builds the table
    structure with placeholder 0 values for computed fields.

    Returns dict with:
        semester_name: str
        title: str (centered title line)
        objectives: [{name, items: [{item, target_score, avg_score, weight_pct}], achievement_rate}]
    """
    # Try wide-format first, then long-format mapping
    wide_data = _parse_wide_eval_table(evaluation_standards)

    if wide_data:
        objectives = []
        for entry in wide_data:
            items = []
            total_weight = 0.0
            for item_entry in entry['items']:
                if isinstance(item_entry, str):
                    # Legacy format: items are plain strings
                    items.append({'item': item_entry, 'target_score': 0, 'avg_score': 0, 'weight_pct': '0%'})
                else:
                    wp = item_entry.get('weight_pct', '0%')
                    ts = _parse_weight_pct_to_target(wp)
                    total_weight += ts
                    items.append({
                        'item': item_entry['item'],
                        'target_score': ts,
                        'avg_score': 0,
                        'weight_pct': wp,
                    })
            # achievement_rate = sum of weight percentage values
            achievement_rate = f'{total_weight:.1f}%' if total_weight == int(total_weight) else f'{total_weight}%'
            if achievement_rate.endswith('.0%'):
                achievement_rate = f'{int(total_weight)}%'
            objectives.append({
                'name': entry['objective'],
                'items': items,
                'achievement_rate': achievement_rate,
            })
    else:
        mapping = _parse_objective_item_mapping(evaluation_standards)
        if mapping:
            # Group by objective
            from collections import OrderedDict
            obj_groups = OrderedDict()
            for m in mapping:
                obj = m['objective']
                if obj not in obj_groups:
                    obj_groups[obj] = []
                obj_groups[obj].append({
                    'item': m['item'],
                    'target_score': 0,
                    'avg_score': 0,
                    'weight_pct': '0%',
                })
            objectives = [
                {
                    'name': obj_name,
                    'items': items,
                    'achievement_rate': '0%',
                }
                for obj_name, items in obj_groups.items()
            ]
        else:
            return None

    if not objectives:
        return None

    title = f'{semester_name} 课程目标达成情况' if semester_name else '课程目标达成情况'

    return {
        'semester_name': semester_name,
        'title': title,
        'objectives': objectives,
    }


def _parse_objectives_list(objectives_text):
    """Parse course objectives text into a list of individual objectives.

    Handles numbered formats like '1. xxx', '目标1：xxx', '（1）xxx', etc.
    """
    import re
    if not objectives_text or objectives_text == '未填写':
        return []

    text = objectives_text.strip()
    # Split by common objective numbering patterns
    patterns = [
        r'(?:课程目标|目标|培养目标)\s*\d+\s*[：:.]',
        r'(?:^|\n)\s*\d+\s*[、.)]',
        r'(?:^|\n)\s*[（(]\s*\d+\s*[）)]',
        r'(?:^|\n)\s*(?:第[一二三四五六七八九十]\s*[条部分章])',
    ]

    combined = '(' + '|'.join(patterns) + ')'
    parts = re.split(combined, text)
    objectives = []
    for part in parts:
        part = part.strip()
        if part and len(part) > 5:
            objectives.append(part)

    if not objectives:
        objectives = [text]

    return objectives


def _match_item_to_column(item_name, score_columns):
    """Fuzzy-match an evaluation item name to a score column header."""
    import re

    def _norm(s):
        return re.sub(r'[（(][^）)]*[）)]', '', s).replace(' ', '').replace('　', '').strip()

    norm_item = _norm(item_name)
    # Exact/normalized match
    for col in score_columns:
        if _norm(col) == norm_item:
            return col
    # Substring match
    for col in score_columns:
        norm_col = _norm(col)
        if len(norm_item) >= 2 and (norm_item in norm_col or norm_col in norm_item):
            return col
    # Jaccard similarity fallback
    best, best_score = None, 0.0
    item_chars = set(norm_item)
    for col in score_columns:
        col_chars = set(_norm(col))
        if not item_chars or not col_chars:
            continue
        j = len(item_chars & col_chars) / len(item_chars | col_chars)
        if j > 0.5 and j > best_score:
            best_score = j
            best = col
    return best


def _compute_objective_achievement(headers, rows, objective_mapping, score_columns,
                                     item_totals=None):
    """Compute per-student per-objective achievement.

    Raw scores may be on different scales across columns (e.g. 课后作业 is
    out of 20 when item_total=20%, while 期末考试 is out of 100).  The
    item_totals dict (from the 合计 row) tells us each column's scale so we
    can normalize every score to a common basis:

        contribution = score × weight_pct / item_total
        rate = sum(contributions) / sum(weight_pct) × 100

    Returns:
        per_student: [{name, objectives: {obj_name: rate_decimal}}, ...]
        objective_items: {obj_name: [(item, target_score, weight_pct), ...]}
        objective_names: ordered list
        item_to_col: {item_name: column_name}
        col_avgs: {column_name: average_raw_score}
        obj_rates: {obj_name: overall_achievement_rate}
    """
    import re

    # Group mapping by objective
    obj_items = {}
    obj_order = []
    for m in objective_mapping:
        obj = m['objective']
        if obj not in obj_items:
            obj_items[obj] = []
            obj_order.append(obj)
        obj_items[obj].append((m['item'], m['target_score'], m['weight_pct']))

    # Match each mapping item to a score column
    item_to_col = {}
    for m in objective_mapping:
        item_name = m['item']
        col = _match_item_to_column(item_name, score_columns)
        if col:
            item_to_col[item_name] = col

    # Find name column
    name_col = None
    for h in headers:
        if '姓名' in str(h).replace(' ', '').strip():
            name_col = h
            break

    # Detect each column's score scale.
    # Some columns are on a 0–100 scale (e.g. 期末考试), others are on their
    # item_total scale (e.g. 课后作业 max=20 when item_total=20%).
    # Normalize everything to 0–100 so the unified formula works:
    #   avg_score = col_avg_100 × weight_pct / 100
    tot = item_totals if item_totals else {}
    col_divisor = {}  # {col_name: divisor} — score / divisor gives percentage
    for col in score_columns:
        col_scores = [_parse_score(row.get(col)) for row in rows]
        col_scores = [s for s in col_scores if s is not None]
        if not col_scores:
            col_divisor[col] = 100
            continue
        col_max = max(col_scores)
        # Find item_total for this column
        item_total = 100
        for item_name, c in item_to_col.items():
            if c == col:
                item_total = tot.get(item_name, 100)
                break
        if col_max > item_total + 1:
            # Scores on 0–100 (or larger) scale → divisor is 100
            col_divisor[col] = 100
        else:
            # Scores on item_total scale → normalize via item_total
            col_divisor[col] = item_total if item_total > 0 else 100

    # Compute per-student achievement with scale-normalized scores.
    per_student = []
    for row in rows:
        name = str(row.get(name_col, '')).strip() if name_col else ''
        student_obj_achievements = {}
        for obj_name, items in obj_items.items():
            total_contrib = 0.0
            total_weight = 0.0
            for item, target_score, weight_pct in items:
                col = item_to_col.get(item)
                if col is None or target_score is None:
                    continue
                score_val = _parse_score(row.get(col))
                if score_val is None:
                    continue
                divisor = col_divisor.get(col, 100)
                if divisor <= 0:
                    continue
                total_contrib += score_val * target_score / divisor
                total_weight += target_score

            if total_weight > 0:
                rate = round(total_contrib / total_weight * 100, 2)
            else:
                rate = 0.0
            student_obj_achievements[obj_name] = rate

        per_student.append({'name': name, 'objectives': student_obj_achievements})

    # Compute column averages, normalized to 0–100 scale.
    col_avgs = {}
    for col in score_columns:
        scores = [_parse_score(row.get(col)) for row in rows]
        scores = [s for s in scores if s is not None]
        if scores:
            raw_avg = sum(scores) / len(scores)
            divisor = col_divisor.get(col, 100)
            if divisor > 0 and divisor != 100:
                col_avgs[col] = round(raw_avg * 100 / divisor, 2)
            else:
                col_avgs[col] = round(raw_avg, 2)

    # Compute overall objective achievement rates
    obj_rates = {}
    for obj_name in obj_order:
        values = [s['objectives'].get(obj_name, 0) for s in per_student]
        if values:
            obj_rates[obj_name] = round(sum(values) / len(values), 2)
        else:
            obj_rates[obj_name] = 0.0

    return {
        'per_student': per_student,
        'objective_items': obj_items,
        'objective_names': obj_order,
        'item_to_col': item_to_col,
        'col_avgs': col_avgs,
        'obj_rates': obj_rates,
    }


def _convert_wide_to_long_mapping(wide_data):
    """Convert wide-format mapping to long-format expected by achievement computation.

    Wide:  [{'objective': str, 'items': [{'item': str, 'weight_pct': str}, ...]}, ...]
           or [{'objective': str, 'items': [str, ...]}, ...]  (legacy format)
    Long:  [{'objective': str, 'item': str, 'target_score': float|None, 'weight_pct': float}, ...]
    """
    result = []
    for entry in wide_data:
        obj = entry['objective']
        for item_entry in entry.get('items', []):
            if isinstance(item_entry, str):
                # Legacy format: items are plain strings, no weight info
                result.append({
                    'objective': obj,
                    'item': item_entry,
                    'target_score': None,
                    'weight_pct': None,
                })
            else:
                wp_str = item_entry.get('weight_pct', '')
                wp_val = _parse_numeric(wp_str) if wp_str else None
                # weight_pct from parser is a percentage (e.g. 4 = 4%).
                # target_score should be the same numeric value for the formula:
                #   contribution = score × target_score / divisor
                #   rate = sum(contributions) / sum(target_scores) × 100
                result.append({
                    'objective': obj,
                    'item': item_entry['item'],
                    'target_score': wp_val,
                    'weight_pct': (wp_val / 100) if wp_val is not None else None,
                })
    return result


def _build_section_5_1_from_items(objective_items, objective_names,
                                    item_to_col=None, col_avgs=None,
                                    item_totals=None, semester_name=''):
    """Build section 5.1 data from the already-computed objective→items mapping.

    Computes:
      target_score = weight_pct number (e.g. '4%' → 4.0)
      avg_score = col_avg_100 × target_score / 100
      achievement_rate = sum(avg_scores) / sum(target_scores) × 100%

    col_avgs are pre-normalized to 0-100 scale by _compute_objective_achievement
    so the formula is unified regardless of each column's original scale.

    Args:
        objective_items: {obj_name: [(item, target_score, weight_pct), ...]}
        objective_names: ordered list of objective names
        item_to_col: {item_name: grade_column_name}  (optional)
        col_avgs: {grade_column_name: average_score_on_0_100_scale}  (optional)
        item_totals: (unused — scale handled upstream, kept for compatibility)
        semester_name: string
    """
    if not objective_names:
        return None

    title = f'{semester_name} 课程目标达成情况' if semester_name else '课程目标达成情况'

    objectives = []
    for obj_name in objective_names:
        items = objective_items.get(obj_name, [])
        built_items = []
        total_weight = 0.0
        for tup in items:
            item_name = tup[0]
            weight_pct = tup[2] if tup[2] is not None else '0%'
            ts = _parse_weight_pct_to_target(weight_pct)
            total_weight += ts

            # avg_score = col_avg × weight_pct / 100
            # col_avg is already normalized to 0-100 scale by _compute_objective_achievement
            avg_score = 0
            if item_to_col and col_avgs:
                col_name = item_to_col.get(item_name)
                if col_name:
                    col_avg = col_avgs.get(col_name, 0)
                    if col_avg > 0:
                        avg_score = round(col_avg * ts / 100, 2)

            built_items.append({
                'item': item_name,
                'target_score': ts,
                'avg_score': avg_score,
                'weight_pct': weight_pct,
            })

        # achievement_rate = sum(avg_scores) / sum(target_scores) × 100%
        if item_to_col and col_avgs and total_weight > 0:
            sum_avg = sum(it['avg_score'] for it in built_items)
            rate = round(sum_avg / total_weight * 100, 2)
            achievement_rate = f'{rate}%'
        else:
            # Fallback: sum of weight percentages
            achievement_rate = f'{int(total_weight)}%'

        objectives.append({
            'name': obj_name,
            'items': built_items,
            'achievement_rate': achievement_rate,
        })

    return {
        'semester_name': semester_name,
        'title': title,
        'objectives': objectives,
    }


def _infer_objective_mapping(objectives_text, score_columns, column_weights,
                              evaluation_standards, headers, rows):
    """Use AI to infer objective-to-evaluation-item mapping when syllabus lacks one.

    NOTE: Zhipu AI call is disabled during early debugging.
    Remove the early-return below to re-enable AI inference.
    """
    # TODO: re-enable Zhipu AI when ready
    return None

    # from course_eval.utils.zhipu import call_zhipu
    #
    # if not objectives_text or objectives_text == '未填写':
    #     return None
    #
    # ... (rest of function)

    obj_list = _parse_objectives_list(objectives_text)
    if not obj_list:
        return None

    col_info_lines = []
    for col in score_columns:
        w = column_weights.get(col) if column_weights else None
        w_str = f'（权重{w:.0f}%）' if w else ''
        col_info_lines.append(f'- {col}{w_str}')
    col_info = '\n'.join(col_info_lines)

    objectives_str = '\n'.join(f'{i+1}. {obj}' for i, obj in enumerate(obj_list))

    prompt = f"""你是一位课程评估专家。请根据课程目标和评价项目，推断每个课程目标对应的评价项目及其目标分值和权重。

【课程目标】
{objectives_str}

【成绩列（评价项目）】
{col_info}

请为每个课程目标列出其对应的评价项目，以JSON数组格式输出。每个元素包含：
- objective: 使用上面列出的完整课程目标文本
- item: 使用上面列出的成绩列名称
- target_score: 目标分值（如果无法确定可以设为null）
- weight_pct: 权重百分比数值（如果无法确定可以设为null）

要求：
1. 每个目标至少对应一个评价项目（一个评价项目可以对应多个目标）
2. 只输出JSON数组，不要包含其他说明文字"""

    try:
        system_prompt = '你是一位课程评估专家。请严格按照要求输出JSON格式，不要包含任何其他文字。'
        result = call_zhipu(system_prompt, prompt)
        if result:
            import re
            match = re.search(r'\[[\s\S]*\]', result)
            if match:
                import json
                mapping = json.loads(match.group())
                if mapping and isinstance(mapping, list) and len(mapping) > 0:
                    return mapping
    except Exception:
        pass

    return None


def _build_achievement_table(objective_items, objective_names, obj_rates,
                               item_to_col, col_avgs):
    """Build Table 6: 课程目标达成情况计算表.

    Columns: 课程目标 | 评价内容 | 目标分值 | 平均得分 | 权重系数 | 课程目标达成情况
    The final column repeats the overall objective achievement rate for every row.
    """
    result = []
    for obj_name in objective_names:
        items = objective_items.get(obj_name, [])
        overall_rate = obj_rates.get(obj_name, 0.0)
        for item, target_score, weight_pct in items:
            col = item_to_col.get(item)
            avg_score = col_avgs.get(col) if col else None
            w_pct = f'{weight_pct}%' if weight_pct else ''
            result.append({
                'objective': obj_name,
                'item': item,
                'target_score': target_score,
                'avg_score': avg_score,
                'weight_pct': w_pct,
                'achievement_rate': f'{overall_rate}%',
            })
    return result


def _build_distribution_table(per_student, objective_names):
    """Build Table 7: 各课程目标达成度分布表.

    Returns:
        objectives: ordered objective names
        avg: average achievement rate per objective
        rows: [{label, counts: [...], pcts: [...]}]
    """
    ranges = [
        ('90%以上', 90, 101),
        ('80%～89%', 80, 90),
        ('70%～79%', 70, 80),
        ('60%～69%', 60, 70),
        ('60%以下', 0, 60),
    ]

    obj_avgs = []
    obj_dists = []

    for obj_name in objective_names:
        values = [s['objectives'].get(obj_name, 0) for s in per_student
                  if obj_name in s['objectives']]
        if values:
            obj_avgs.append(round(sum(values) / len(values), 2))
        else:
            obj_avgs.append(0.0)

        dist = {}
        for label, lo, hi in ranges:
            count = sum(1 for v in values if lo <= v < hi)
            pct = round(count / len(values) * 100, 2) if values else 0
            dist[label] = {'count': count, 'pct': pct}
        obj_dists.append(dist)

    dist_rows = []
    for label, lo, hi in ranges:
        dist_rows.append({
            'label': label,
            'counts': [obj_dists[oi].get(label, {}).get('count', 0) for oi in range(len(objective_names))],
            'pcts': [obj_dists[oi].get(label, {}).get('pct', 0) for oi in range(len(objective_names))],
        })

    return {
        'objectives': objective_names,
        'avg': obj_avgs,
        'rows': dist_rows,
    }


def _build_low_achievement_table(per_student, objective_names, total_scores=None):
    """Build Table 8: 未达成课程目标学生汇总表.

    Only includes students whose 总评成绩 (total score) is below 60.
    If total_scores is not provided, falls back to the old behavior of
    including any student with an objective rate below 60%.

    Values shown as decimals (e.g., 0.46) matching the template format.
    """
    low_students = []
    for s in per_student:
        name = s['name']
        if total_scores is not None:
            score = total_scores.get(name)
            if score is None or score >= 60:
                continue

        achievements = {}
        for obj_name in objective_names:
            rate = s['objectives'].get(obj_name, 0)
            decimal_val = round(rate / 100, 2)
            achievements[obj_name] = decimal_val
        low_students.append({'name': name, 'achievements': achievements})
    return low_students


def _build_per_objective_analysis_prompt(obj_name, obj_rate, course_name, objectives_text):
    """Build prompt for single-objective AI analysis."""
    return f"""你是一位大学课程评估专家。请对以下课程目标的达成情况进行简要分析。

课程名称：{course_name}

{obj_name}：达成度为{obj_rate}%

课程目标全文：
{objectives_text}

请写一段约100-150字的分析，说明该目标的达成水平如何、可能的原因以及改进方向。
直接输出分析内容，不需要"课程目标X的达成情况分析"之类的标题。"""


def _generate_per_objective_analysis(obj_name, obj_rate, course_name, objectives_text):
    """Generate AI analysis for a single objective.

    NOTE: Zhipu AI call is disabled during early debugging.
    Remove the early-return below to re-enable AI generation.
    """
    # TODO: re-enable Zhipu AI when ready
    # try:
    #     from course_eval.utils.zhipu import call_zhipu
    #     system_prompt = '你是一位经验丰富的大学课程评估专家。'
    #     user_prompt = _build_per_objective_analysis_prompt(
    #         obj_name, obj_rate, course_name, objectives_text)
    #     result = call_zhipu(system_prompt, user_prompt)
    #     if result:
    #         return result
    # except Exception:
    #     pass

    # Fallback
    if obj_rate >= 90:
        level = '优秀'
    elif obj_rate >= 80:
        level = '良好'
    elif obj_rate >= 70:
        level = '中等'
    elif obj_rate >= 60:
        level = '及格'
    else:
        level = '待改进'
    return f'{obj_name}的达成度为{obj_rate}%，达成水平为"{level}"。基于学生成绩数据分析，该目标的达成情况总体较好，建议持续关注并优化相关教学环节。'


def _build_radar_chart_data(objective_names, obj_rates):
    """Build radar chart data for overall objective achievement visualization."""
    return {
        'labels': objective_names,
        'values': [obj_rates.get(obj, 0) for obj in objective_names],
    }


def _get_fallback_module5():
    """Fallback when data-driven generation fails."""
    return {
        'report_title': '',
        'objectives': [],
        'achievement_table': [],
        'distribution_table': None,
        'per_objective_analysis': [],
        'low_students': [],
        'radar_data': {'labels': [], 'values': []},
        'student_achievements': [],
        'overall_avg_achievement': 0,
        'section_5_1': None,
        'generated': False,
    }


def generate_module_5(course_name='', objectives='', evaluation_standards=None,
                      grades_file=None, user_id=None, semester_name=''):
    """Generate Module 5: Course Objective Achievement Degree.

    Matches the template structure:
      (5.1) 课程目标达成情况 → Summary overview table
      (1) 统计分析 → Table 6 (achievement calc) + Table 7 (distribution)
      (2) 图形分析 → Charts (radar + per-objective distribution)
      (3) 教学班整体课程目标达成情况分析 → Per-objective AI analysis
      (4) 学生个体课程目标达成情况分析 → Table 8 (low students)

    Formula: achievement = sum(raw_scores) / sum(target_scores) * 100
    """
    import re

    if not grades_file or not user_id:
        result = _get_fallback_module5()
        result['section_5_1'] = _generate_section_5_1(evaluation_standards, semester_name)
        return result

    try:
        grades_data = get_effective_data(grades_file, user_id)
    except Exception:
        result = _get_fallback_module5()
        result['section_5_1'] = _generate_section_5_1(evaluation_standards, semester_name)
        return result

    headers = grades_data['headers']
    rows = grades_data['rows']

    # Identify score columns
    name_col_index = _find_name_column_index(headers)
    score_columns = []
    for i, col in enumerate(headers):
        col_values = [row.get(col) for row in rows if col in row]
        if _is_score_column(col, col_values, i, name_col_index):
            score_columns.append(col)

    if not score_columns:
        result = _get_fallback_module5()
        result['section_5_1'] = _generate_section_5_1(evaluation_standards, semester_name)
        return result

    # Extract weights and objective mapping from evaluation standards.
    # Try wide-format first — long-format parser can falsely match wide tables
    # because spanning headers like "评价依据及成绩比例(%)" contain "评价".
    item_weights_map = _extract_score_weights(evaluation_standards) if evaluation_standards else None
    objective_mapping = None

    wide_data = _parse_wide_eval_table(evaluation_standards) if evaluation_standards else None
    if wide_data:
        objective_mapping = _convert_wide_to_long_mapping(wide_data)
    else:
        objective_mapping = _parse_objective_item_mapping(evaluation_standards) if evaluation_standards else None

    if not objective_mapping:
        column_weights = _match_score_weights(score_columns, item_weights_map) if item_weights_map else {}
        objective_mapping = _infer_objective_mapping(
            objectives, score_columns, column_weights,
            evaluation_standards, headers, rows)

    if not objective_mapping:
        result = _get_fallback_module5()
        result['section_5_1'] = _generate_section_5_1(evaluation_standards, semester_name)
        return result

    # Parse 合计 row from syllabus for per-column scale normalization
    item_totals = _parse_eval_item_totals(evaluation_standards)

    # Compute per-student achievement
    ach_data = _compute_objective_achievement(
        headers, rows, objective_mapping, score_columns, item_totals)

    per_student = ach_data['per_student']
    objective_items = ach_data['objective_items']
    objective_names = ach_data['objective_names']
    item_to_col = ach_data['item_to_col']
    col_avgs = ach_data['col_avgs']
    obj_rates = ach_data['obj_rates']

    if not objective_names:
        result = _get_fallback_module5()
        result['section_5_1'] = _generate_section_5_1(evaluation_standards, semester_name)
        return result

    # Build section 5.1 from the computed objective_items
    section_5_1 = _build_section_5_1_from_items(objective_items, objective_names,
                                                    item_to_col, col_avgs,
                                                    item_totals, semester_name)

    # Build Table 6: 课程目标达成情况计算表
    achievement_table = _build_achievement_table(
        objective_items, objective_names, obj_rates, item_to_col, col_avgs)

    # Build Table 7: 各课程目标达成度分布表
    distribution_table = _build_distribution_table(per_student, objective_names)

    # Extract total scores (总评成绩) for filtering Table 8
    total_score_col = None
    for h in headers:
        norm = str(h).replace(' ', '').strip()
        if norm in ('总评', '总评成绩', '总分', '总成绩'):
            total_score_col = h
            break
    if not total_score_col:
        # Fuzzy match: column name contains any of these keywords
        for h in headers:
            norm = str(h).replace(' ', '').strip()
            if '总评' in norm or '总分' in norm or '总成绩' in norm:
                total_score_col = h
                break

    total_scores = {}
    if total_score_col:
        name_col = None
        for h in headers:
            if '姓名' in str(h).replace(' ', '').strip():
                name_col = h
                break
        for row in rows:
            name = str(row.get(name_col, '')).strip() if name_col else ''
            if name:
                score = _parse_score(row.get(total_score_col))
                if score is not None:
                    total_scores[name] = score

    # Build Table 8: 未达成课程目标学生汇总表
    low_students = _build_low_achievement_table(
        per_student, objective_names, total_scores if total_scores else None)

    # Per-objective AI analysis for section (3)
    per_objective_analysis = []
    for obj_name in objective_names:
        rate = obj_rates.get(obj_name, 0)
        analysis = _generate_per_objective_analysis(obj_name, rate, course_name, objectives)
        per_objective_analysis.append({
            'objective': obj_name,
            'rate': rate,
            'analysis': analysis,
        })

    # Radar chart data
    radar_data = _build_radar_chart_data(objective_names, obj_rates)

    # Per-student average achievement for scatter chart
    student_achievements = []
    for s in per_student:
        vals = list(s['objectives'].values())
        avg_val = round(sum(vals) / len(vals), 2) if vals else 0.0
        student_achievements.append({
            'name': s['name'],
            'avg_achievement': avg_val,
        })
    overall_avg = round(
        sum(s['avg_achievement'] for s in student_achievements) / len(student_achievements), 2
    ) if student_achievements else 0.0

    return {
        'report_title': f'{course_name} 课程目标达成情况',
        'objectives': objective_names,
        'achievement_table': achievement_table,
        'distribution_table': distribution_table,
        'per_objective_analysis': per_objective_analysis,
        'low_students': low_students,
        'radar_data': radar_data,
        'student_achievements': student_achievements,
        'overall_avg_achievement': overall_avg,
        'section_5_1': section_5_1,
        'generated': True,
    }


def generate_module_6(context=None):
    """Generate Module 6: Continuous Improvement Plan.

    Args:
        context: Optional dict with keys course_name, objectives, grade_summary.
                 If provided, calls Zhipu AI. Falls back to template on failure.
    """
    if context and context.get('course_name'):
        try:
            from course_eval.utils.zhipu import call_zhipu

            system_prompt = '你是一位经验丰富的大学教学督导专家，擅长撰写课程持续改进方案。请严格按照要求的格式和结构输出内容。'
            user_prompt = _build_module6_prompt(context)
            result = call_zhipu(system_prompt, user_prompt)

            if result:
                return _parse_module6_response(result)
        except Exception:
            pass

    return _get_fallback_module6()


# ── Full report orchestrator ────────────────────────────────────────────────

def generate_report(user_id, course_id, class_id, semester_name):
    """Orchestrate full report generation and return the report data dict."""

    course = get_object_or_404(Course, id=course_id, user_id=user_id)
    class_group = get_object_or_404(ClassGroup, id=class_id, user_id=user_id)
    semester, _ = Semester.objects.get_or_create(name=semester_name, user_id=user_id)

    syllabus_file = _find_file(course_id, class_id, semester, user_id, 'syllabus')
    student_info_file = _find_file(course_id, class_id, semester, user_id, 'student_info')
    grades_file = _find_file(course_id, class_id, semester, user_id, 'grades')

    # Parse syllabus once
    syllabus_fields = _parse_syllabus(syllabus_file)
    raw_table_kv = syllabus_fields.pop('_all_table_kv', {})

    # Student info stats
    student_stats = {}
    if student_info_file:
        info_data = get_effective_data(student_info_file, user_id)
        student_stats = _analyze_student_info(info_data['headers'], info_data['rows'])

    evaluation_standards = syllabus_fields.get('evaluation_standards')

    # Get title metadata from student_info and grades files for course identity fields
    student_info_meta = _get_file_metadata(course_id, class_id, semester, user_id, 'student_info')
    grades_meta = _get_file_metadata(course_id, class_id, semester, user_id, 'grades')

    module_1 = generate_module_1(course, class_group, syllabus_fields, student_stats, raw_table_kv, grades_meta, student_info_meta)
    module_2 = generate_module_2(syllabus_fields)
    module_4 = generate_module_4(grades_file, user_id, evaluation_standards)

    report_data = {
        'module_1_course_info': module_1,
        'module_2_objectives': module_2,
        'module_3_evaluation_standards': generate_module_3(syllabus_fields),
        'module_4_evaluation_results': module_4,
        'module_5_objective_achievement': generate_module_5(
            course.name, module_2, evaluation_standards, grades_file, user_id,
            semester_name=semester.name,
        ),
        'module_6_improvement_plan': generate_module_6(
            _build_module6_context(course.name, module_2, module_4)
        ),
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
