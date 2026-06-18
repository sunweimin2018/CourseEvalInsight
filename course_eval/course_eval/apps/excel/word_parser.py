import os
import re
from docx import Document


# ── Heading / section marker keywords ──────────────────────────────────────────
# Ordered roughly by typical syllabus layout; used to detect section boundaries.
SECTION_HEADINGS = [
    '课程考核及成绩评定',
    '课程考核与成绩评定',
    '考核及成绩评定',
    '考核与成绩评定',
    '成绩评定',
    '课程教材',
    '教材及参考资料',
    '教材与参考资料',
    '参考教材及网站',
    '参考教材与网站',
    '课程目标',
    '教学目标',
]

# Labels that map directly to simple single-value fields (label: value pattern).
SIMPLE_FIELD_LABELS = {
    '课程名称': 'course_name',
    '课程编号': 'course_code',
    '授课班级': 'teaching_class',
    '开课院系': 'department',
    '授课单位': 'department',
    '开课单位': 'department',
    '课程性质': 'course_nature',
    '课程类型': 'course_type',
    '修课人数': 'student_count',
    '课序号': 'course_seq',
    '总学时': 'total_hours',
    '学时数': 'total_hours',
    '学时': 'total_hours',
    '学分': 'credits',
    '授课教师': 'teacher',
    '执笔人': 'teacher',
}


def _normalize(text):
    """Collapse whitespace for reliable matching."""
    return re.sub(r'\s+', '', text)


def _is_heading(para_text, targets):
    """Check whether *para_text* is one of the *targets* (after stripping numbering prefixes).

    Only matches when the cleaned text is exactly equal to a target, preventing
    false matches like "课程目标" inside "课程目标1：系统掌握...".
    """
    t = _normalize(para_text)
    cleaned = re.sub(r'^[（(][一二三四五六七八九十\d]+[）)]', '', t)
    cleaned = re.sub(r'^[一二三四五六七八九十]+[、.]', '', cleaned)
    cleaned = re.sub(r'^\d+[、.)\s]+', '', cleaned)
    cleaned = cleaned.strip()
    for target in targets:
        if cleaned == _normalize(target):
            return target
    return None


def _find_section_range(paragraphs, start_heading, end_headings):
    """Return (start_idx, end_idx) for the section bounded by headings.

    *start_heading* can be a string or list of strings (alternate names).
    *end_headings* is a list of heading texts that terminate the section.
    Returns (None, None) if the start heading is not found.
    """
    start_targets = [start_heading] if isinstance(start_heading, str) else start_heading
    start_idx = None
    for i, p in enumerate(paragraphs):
        if _is_heading(p['text'], start_targets):
            start_idx = i
            break
    if start_idx is None:
        return None, None

    end_idx = len(paragraphs)
    for i in range(start_idx + 1, len(paragraphs)):
        if _is_heading(paragraphs[i]['text'], end_headings):
            end_idx = i
            break
    return start_idx, end_idx


def _collect_paragraph_text(paragraphs, start_idx, end_idx):
    """Join paragraph texts in [start_idx, end_idx) with newlines."""
    texts = []
    for i in range(start_idx, end_idx):
        t = paragraphs[i]['text'].strip()
        if t:
            texts.append(t)
    return '\n'.join(texts)


def _extract_from_tables(tables):
    """Walk all table cells looking for label:value pairs.

    Handles two patterns:
    1. Same-cell: "课程名称：程序设计基础" (label + value in one cell)
    2. Adjacent-cell: "课程名称：" in cell[i], "程序设计基础" in cell[i+1]
    """
    fields = {}
    for table in tables:
        all_rows = [table['headers']] + table['rows']
        for row in all_rows:
            # Pattern 1: Same-cell label:value
            for i, cell_text in enumerate(row):
                for label, key in SIMPLE_FIELD_LABELS.items():
                    if key in fields:
                        continue
                    norm_cell = _normalize(cell_text)
                    pattern = re.escape(_normalize(label)) + r'[：:\s]+(.+)'
                    m = re.search(pattern, norm_cell)
                    if m and m.group(1).strip():
                        fields[key] = m.group(1).strip()
                        break

            # Pattern 2: Adjacent-cell — label in cell[i], value in cell[i+1]
            for i, cell_text in enumerate(row):
                if i + 1 >= len(row):
                    continue
                norm_cell = _normalize(cell_text)
                for label, key in SIMPLE_FIELD_LABELS.items():
                    if key in fields:
                        continue
                    label_colon = _normalize(label) + '：'
                    label_colon2 = _normalize(label) + ':'
                    if norm_cell == label_colon or norm_cell == label_colon2 \
                            or norm_cell.endswith(label_colon) or norm_cell.endswith(label_colon2):
                        val = row[i + 1].strip()
                        if val and not any(
                            _normalize(val) in (_normalize(l), _normalize(l) + '：', _normalize(l) + ':')
                            for l in SIMPLE_FIELD_LABELS
                        ):
                            fields[key] = val
                            break
    return fields


def _extract_labeled_fields(paragraphs):
    """Extract simple fields from paragraphs that contain label:value patterns."""
    fields = {}
    for p in paragraphs:
        text = p['text'].strip()
        for label, key in SIMPLE_FIELD_LABELS.items():
            if key in fields:
                continue
            # Try "label：value" or "label: value"
            m = re.match(re.escape(label) + r'\s*[：:]\s*(.+)', text)
            if m:
                val = m.group(1).strip()
                if val:
                    fields[key] = val
                break
    return fields


def extract_syllabus_fields(paragraphs, tables):
    """Extract structured syllabus fields from parsed .docx content.

    Returns a dict with keys matching the report template fields.
    Missing fields default to ``"未填写"``.
    """
    # 1. Simple fields from tables
    fields = _extract_from_tables(tables)

    # 2. Simple fields from labeled paragraphs (fill gaps)
    para_fields = _extract_labeled_fields(paragraphs)
    for k, v in para_fields.items():
        if k not in fields:
            fields[k] = v

    # 3. 课程目标 — content under "课程目标" heading, excluding the heading's own
    #    accompanying table and table captions.
    start, end = _find_section_range(
        paragraphs,
        ['课程目标', '教学目标'],
        SECTION_HEADINGS,
    )
    if start is not None:
        # Collect paragraph text only (skip the heading line itself).
        # Table content near the heading is filtered by collecting only
        # paragraphs, not table data — the heading's "table说明" is typically
        # a short paragraph right after the heading; we include everything
        # that is not a structural heading.
        texts = []
        for i in range(start + 1, end):
            t = paragraphs[i]['text'].strip()
            if t:
                texts.append(t)
        if texts:
            fields['course_objectives'] = '\n'.join(texts)

    # 4. 选用教材 — content under "教材及参考资料" > "课程教材",
    #    excluding "参考教材及网站" content.
    textbook_start, textbook_end = _find_section_range(
        paragraphs,
        '课程教材',
        SECTION_HEADINGS,
    )
    if textbook_start is not None:
        ref_start, _ = _find_section_range(
            paragraphs,
            ['参考教材及网站', '参考教材与网站'],
            [],
        )
        effective_end = ref_start if ref_start is not None else textbook_end
        texts = []
        for i in range(textbook_start + 1, effective_end):
            t = paragraphs[i]['text'].strip()
            if t:
                texts.append(t)
        if texts:
            fields['textbook'] = '\n'.join(texts)

    # 5. 课程考核及成绩评定 — content from its heading up to the next major heading
    #    ("教材及参考资料" or similar).
    eval_start, eval_end = _find_section_range(
        paragraphs,
        ['课程考核及成绩评定', '课程考核与成绩评定', '考核及成绩评定', '考核与成绩评定'],
        SECTION_HEADINGS,
    )
    if eval_start is not None:
        texts = []
        for i in range(eval_start + 1, eval_end):
            t = paragraphs[i]['text'].strip()
            if t:
                texts.append(t)
        if texts:
            fields['evaluation_standards'] = '\n'.join(texts)

    # 6. Fill defaults for all expected fields
    all_keys = (
        list(SIMPLE_FIELD_LABELS.values())
        + ['course_objectives', 'textbook', 'evaluation_standards']
    )
    for k in all_keys:
        if k not in fields:
            fields[k] = '未填写'

    return fields


def parse_docx(file_path):
    """Parse a .docx file and return its paragraphs and tables."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext != '.docx':
        return {'error': '仅支持 .docx 格式在线预览，.doc 文件请先转换为 .docx'}

    doc = Document(file_path)

    paragraphs = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style else 'Normal'
        paragraphs.append({
            'index': idx,
            'text': text,
            'style': style,
        })

    tables = []
    for t_idx, table in enumerate(doc.tables):
        rows = []
        headers = []
        for r_idx, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            if r_idx == 0:
                headers = cells
            else:
                rows.append(cells)
        tables.append({
            'index': t_idx,
            'headers': headers,
            'rows': rows,
        })

    return {
        'paragraphs': paragraphs,
        'tables': tables,
    }
