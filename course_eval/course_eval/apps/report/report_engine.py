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


def _extract_score_segments(evaluation_standards):
    """Extract score segment definitions from syllabus evaluation_standards blocks.

    Returns a list of dicts: [{'label': str, 'lo': float, 'hi': float}, ...]
    or None if no usable table is found.
    """
    if not evaluation_standards or not isinstance(evaluation_standards, list):
        return None

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

        segments = []
        # Skip first column (usually "考核项目") and iterate middle columns
        for c in range(1, num_cols):
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

        if segments:
            return segments

    return None


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


def _analyze_grades(headers, rows, segments=None):
    """Compute statistics for each numeric score column.

    Args:
        segments: Optional list of dicts [{'label', 'lo', 'hi'}] from syllabus.
                  If None or empty, falls back to hardcoded SCORE_BUCKETS.
    """
    name_col_index = _find_name_column_index(headers)
    score_columns = []
    for i, col in enumerate(headers):
        col_values = [row.get(col) for row in rows if col in row]
        if _is_score_column(col, col_values, i, name_col_index):
            score_columns.append(col)

    # Build segment definitions
    use_segments = segments if segments else SCORE_BUCKETS

    analysis = {}
    for col in score_columns:
        raw = [_parse_score(row.get(col)) for row in rows]
        scores = [s for s in raw if s is not None]
        missing_count = len(raw) - len(scores)

        if not scores:
            continue

        dist = {}
        if segments:
            for seg in segments:
                count = sum(1 for s in scores if seg['lo'] <= s < seg['hi'])
                dist[seg['label']] = {'label': seg['label'], 'count': count}
        else:
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


# ── Per-module generation functions ────────────────────────────────────────

def generate_module_1(course, class_group, syllabus_fields, student_stats, raw_table_kv):
    """Generate Module 1: Course Basic Information Table."""
    return {
        'course_name': syllabus_fields.get('course_name', course.name),
        'course_code': syllabus_fields.get('course_code', '未填写'),
        'teaching_class': '、'.join(student_stats.get('classes', [])) or syllabus_fields.get('teaching_class', class_group.name),
        'student_count': student_stats.get('total', '未填写'),
        'course_seq': syllabus_fields.get('course_seq', '未填写'),
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

    Args:
        evaluation_standards: Optional list of blocks from syllabus parsing.
            Used to extract score segment definitions dynamically.
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
    segments = _extract_score_segments(evaluation_standards)
    fallback = segments is None

    # Build segment_labels for table header
    if segments:
        segment_labels = [s['label'] for s in segments]
    else:
        segment_labels = [label for _, label, _, _ in SCORE_BUCKETS]

    grade_analysis = _analyze_grades(grades_data['headers'], grades_data['rows'], segments)

    # Build new sections format (without AI summaries first)
    sections = []
    future_tasks = []  # (section_index, callable) for parallel AI generation

    for col_name, stats in grade_analysis.items():
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
        }
        sections.append(section_data)
        # Prepare AI summary task for parallel execution
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
                    pass  # keep empty string
        except TimeoutError:
            pass  # AI summaries are best-effort, don't block the response
        finally:
            executor.shutdown(wait=False)

    return {
        'sections': sections,
        'segment_labels': segment_labels,
        'generated': bool(grade_analysis),
        'fallback': fallback,
        'grade_analysis': grade_analysis,
        'score_columns': list(grade_analysis.keys()),
    }


def _build_module5_context(course_name, objectives, module_4):
    """Build a context dict for Module 5 AI generation from Modules 1/2/4 data."""
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


def _build_module5_prompt(context):
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


def _parse_module5_response(text):
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


def _get_fallback_module5():
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


def generate_module_5(context=None):
    """Generate Module 5: Continuous Improvement Plan.

    Args:
        context: Optional dict with keys course_name, objectives, grade_summary.
                 If provided, calls Zhipu AI. Falls back to template on failure.
    """
    if context and context.get('course_name'):
        try:
            from course_eval.utils.zhipu import call_zhipu

            system_prompt = '你是一位经验丰富的大学教学督导专家，擅长撰写课程持续改进方案。请严格按照要求的格式和结构输出内容。'
            user_prompt = _build_module5_prompt(context)
            result = call_zhipu(system_prompt, user_prompt)

            if result:
                return _parse_module5_response(result)
        except Exception:
            pass

    return _get_fallback_module5()


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
    module_1 = generate_module_1(course, class_group, syllabus_fields, student_stats, raw_table_kv)
    module_2 = generate_module_2(syllabus_fields)
    module_4 = generate_module_4(grades_file, user_id, evaluation_standards)

    # Build context for Module 5 AI generation
    module5_context = _build_module5_context(course.name, module_2, module_4)

    report_data = {
        'module_1_course_info': module_1,
        'module_2_objectives': module_2,
        'module_3_evaluation_standards': generate_module_3(syllabus_fields),
        'module_4_evaluation_results': module_4,
        'module_5_improvement_plan': generate_module_5(module5_context),
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
