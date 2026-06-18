import os
import re
from docx import Document
from docx.oxml.shared import qn

# ── Wingdings 2 checkbox symbol mapping ────────────────────────────────────
_SYM_CHECKED = '☑'
_SYM_UNCHECKED = '☐'

_WINGDINGS2_MAP = {
    '00A3': _SYM_UNCHECKED,  # Wingdings 2 0xA3 → ☐
    'F052': _SYM_CHECKED,    # Wingdings 2 0xF052 → ☑
}

# ── Section heading keywords ────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════════
# Low-level cell text extraction (preserves checkbox / symbol state)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_cell_text(tc):
    """Extract cell text including symbol characters (Wingdings checkboxes).

    Walks ``w:r`` and ``w:sym`` elements so that ☑/☐ states are preserved.
    """
    paras = tc.findall('.//' + qn('w:p'))
    lines = []
    for p in paras:
        line_parts = []
        for r_elem in p.findall(qn('w:r')):
            for sym in r_elem.findall(qn('w:sym')):
                font = sym.get(qn('w:font'), '')
                char = sym.get(qn('w:char'), '')
                if 'Wingdings 2' in font and char in _WINGDINGS2_MAP:
                    line_parts.append(_WINGDINGS2_MAP[char])
            for t_elem in r_elem.findall(qn('w:t')):
                if t_elem.text:
                    line_parts.append(t_elem.text)
        lines.append(''.join(line_parts))
    return '\n'.join(lines).strip().replace('\n', ' ')


# ══════════════════════════════════════════════════════════════════════════════
# Merged-cell-aware table parsing
# ══════════════════════════════════════════════════════════════════════════════

def _get_merged_cell_map(table):
    """Parse a Word table handling gridSpan / vMerge / hMerge.

    Returns (merged_map, origins) where:
      merged_map: (row, grid_col) → cell text (with checkboxes)
      origins:    (row, grid_col) → (source_row, source_grid_col)
    """
    merged_map = {}
    origins = {}
    num_rows = len(table.rows)

    for row_idx, row in enumerate(table.rows):
        tr = row._tr
        tc_elements = tr.findall(qn('w:tc'))
        grid_col = 0

        for tc in tc_elements:
            tcpr = tc.find(qn('w:tcPr'))

            # gridSpan
            gs = 1
            if tcpr is not None:
                gs_el = tcpr.find(qn('w:gridSpan'))
                if gs_el is not None:
                    gs = int(gs_el.get(qn('w:val')))

            # vMerge / hMerge
            vm_val = None
            hm_val = None
            if tcpr is not None:
                vm_el = tcpr.find(qn('w:vMerge'))
                if vm_el is not None:
                    vm_val = vm_el.get(qn('w:val'), 'continue')
                hm_el = tcpr.find(qn('w:hMerge'))
                if hm_el is not None:
                    hm_val = hm_el.get(qn('w:val'), 'continue')

            cell_text = _extract_cell_text(tc)
            origin = (row_idx, grid_col)

            if vm_val == 'continue':
                grid_col += gs
                continue

            # Vertical merge — fill all rows
            if vm_val == 'restart':
                r = row_idx
                while r < num_rows:
                    for c in range(grid_col, grid_col + gs):
                        merged_map[(r, c)] = cell_text
                        origins[(r, c)] = origin
                    r += 1
                    if r >= num_rows:
                        break
                    next_tr = table.rows[r]._tr
                    next_tcs = next_tr.findall(qn('w:tc'))
                    g = 0
                    found_continue = False
                    for next_tc in next_tcs:
                        n_tcpr = next_tc.find(qn('w:tcPr'))
                        n_gs = 1
                        if n_tcpr is not None:
                            n_gs_el = n_tcpr.find(qn('w:gridSpan'))
                            if n_gs_el is not None:
                                n_gs = int(n_gs_el.get(qn('w:val')))
                        if g == grid_col:
                            n_vm_el = n_tcpr.find(qn('w:vMerge')) if n_tcpr is not None else None
                            if n_vm_el is not None:
                                found_continue = True
                            break
                        g += n_gs
                    if not found_continue:
                        break

            # Horizontal merge — fill all columns
            elif hm_val == 'restart':
                for c in range(grid_col, grid_col + gs):
                    merged_map[(row_idx, c)] = cell_text
                    origins[(row_idx, c)] = origin

            # Normal cell
            else:
                for c in range(grid_col, grid_col + gs):
                    merged_map[(row_idx, c)] = cell_text
                    origins[(row_idx, c)] = origin

            grid_col += gs

    return merged_map, origins


def _collect_row_cells(merged_map, origins, row_idx, max_grid_col):
    """Collect distinct logical cells in a row, ordered by grid column."""
    seen_origins = set()
    cells = []
    for col_idx in range(max_grid_col + 1):
        text = merged_map.get((row_idx, col_idx))
        if not text:
            continue
        origin = origins.get((row_idx, col_idx))
        if origin not in seen_origins:
            seen_origins.add(origin)
            cells.append((col_idx, text))
    return cells


def _build_table_grid(merged_map, origins, num_rows, num_cols):
    """Build a grid representation of a table with cell span information.

    Returns a list of rows, each a list where:
      - {'text': ..., 'colspan': N, 'rowspan': M} marks a cell that starts here
      - None marks a position covered by a spanning cell
    """
    grid = [[None] * num_cols for _ in range(num_rows)]

    origin_cells = {}
    for (r, c), origin in origins.items():
        origin_cells.setdefault(origin, []).append((r, c))

    for origin, positions in origin_cells.items():
        src_r, src_c = origin
        rows = [p[0] for p in positions]
        cols = [p[1] for p in positions]
        rowspan = max(rows) - min(rows) + 1
        colspan = max(cols) - min(cols) + 1
        text = merged_map.get((src_r, src_c), '')
        grid[src_r][src_c] = {'text': text, 'colspan': colspan, 'rowspan': rowspan}

    return grid


def _extract_all_table_kv(tables_rich):
    """Extract ALL key-value pairs from every table using the rich cell data.

    Pairs adjacent cells within each row (key → value). Also handles
    vMerge rows where a header spans two rows and sub-keys sit beside values.
    """
    all_kv = {}
    for t_idx, t in enumerate(tables_rich):
        merged_map = t['merged_map']
        origins = t['origins']
        num_rows = t['num_rows']

        max_grid_col = 0
        for (_r, c) in merged_map:
            if c > max_grid_col:
                max_grid_col = c

        table_kv = {}
        skip_rows = set()

        for row_idx in range(num_rows):
            if row_idx in skip_rows:
                continue

            row_cells = _collect_row_cells(merged_map, origins, row_idx, max_grid_col)

            # Detect vMerge: if next row's first-cell origin is the current row
            next_row = row_idx + 1
            if next_row < num_rows:
                header_row = None
                for col_idx in range(max_grid_col + 1):
                    origin = origins.get((next_row, col_idx))
                    if origin is not None:
                        if origin[0] < next_row:
                            header_row = origin[0]
                        break

                if header_row == row_idx:
                    next_cells = _collect_row_cells(merged_map, origins, next_row, max_grid_col)
                    main_key = next_cells[0][1] if next_cells else ''
                    # Remove shared first cell from the sub-row
                    if row_cells and next_cells and row_cells[0][1] == next_cells[0][1]:
                        next_cells = next_cells[1:]
                    sub_keys = row_cells[1:]
                    next_col_map = {col: text for col, text in next_cells}

                    for sk_col, sk_text in sub_keys:
                        value = next_col_map.get(sk_col, '')
                        if value:
                            full_key = f'{main_key}{sk_text}' if main_key else sk_text
                            table_kv[full_key] = value

                    skip_rows.add(next_row)
                    continue

            # Normal row: pair adjacent cells as key → value
            texts = [t for _, t in row_cells]
            for i in range(0, len(texts) - 1, 2):
                key = texts[i]
                value = texts[i + 1]
                if key:
                    table_kv[key] = value

        all_kv.update(table_kv)
    return all_kv


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

def _normalize(text):
    return re.sub(r'\s+', '', text)


TABLE_GUIDE_PATTERNS = [
    re.compile(r'如下表[所示]*'),
    re.compile(r'下表[所示]*'),
    re.compile(r'对应关系[表图]*'),
    re.compile(r'如下[所示]*[：:]'),
    re.compile(r'[表图]如下'),
]

def _is_table_guide(text):
    """Check if a paragraph is a table/figure guide caption that should be excluded."""
    clean = _normalize(text)
    if not clean:
        return False
    for pat in TABLE_GUIDE_PATTERNS:
        if pat.search(clean):
            return True
    return False


def _is_heading(para_text, targets):
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


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def parse_docx(file_path):
    """Parse a .docx file and return its paragraphs and tables.

    Tables are parsed with merged-cell awareness and checkbox state preserved.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext != '.docx':
        return {'error': '仅支持 .docx 格式在线预览，.doc 文件请先转换为 .docx'}

    doc = Document(file_path)

    # ── Paragraphs ──────────────────────────────────────────────────────
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

    # ── Tables (rich: merged-cell-aware with checkbox symbols) ─────────
    tables = []
    tables_rich = []
    for t_idx, table in enumerate(doc.tables):
        merged_map, origins = _get_merged_cell_map(table)

        max_grid_col = 0
        for (_r, c) in merged_map:
            if c > max_grid_col:
                max_grid_col = c

        # Build simplified row view for display / API compatibility
        rows = []
        for r_idx in range(len(table.rows)):
            cells = _collect_row_cells(merged_map, origins, r_idx, max_grid_col)
            rows.append([t for _, t in cells])

        tables.append({
            'index': t_idx,
            'headers': rows[0] if rows else [],
            'rows': rows[1:] if len(rows) > 1 else [],
        })

        # Keep rich data for KV extraction
        tables_rich.append({
            'index': t_idx,
            'merged_map': merged_map,
            'origins': origins,
            'num_rows': len(table.rows),
        })

    # ── Build body element order (interleaved paragraphs and tables) ────
    para_lookup = {p['index']: i for i, p in enumerate(paragraphs)}
    body_elements = []
    p_idx = 0
    t_idx = 0
    for child in doc.element.body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'p':
            if p_idx in para_lookup:
                body_elements.append({'type': 'p', 'text': paragraphs[para_lookup[p_idx]]['text']})
            p_idx += 1
        elif tag == 'tbl':
            if t_idx < len(tables_rich):
                rich = tables_rich[t_idx]
                max_grid_col = max((c for (_r, c) in rich['merged_map']), default=-1)
                num_cols = max_grid_col + 1
                grid = _build_table_grid(rich['merged_map'], rich['origins'], rich['num_rows'], num_cols)
                body_elements.append({'type': 't', 'num_cols': num_cols, 'grid': grid})
            t_idx += 1

    return {
        'paragraphs': paragraphs,
        'tables': tables,
        '_tables_rich': tables_rich,
        '_body_elements': body_elements,
    }


def _extract_section_blocks(body_elements, start_headings, end_headings):
    """Extract content blocks (paragraphs + tables) within a section boundary.

    Returns a list of blocks:
      {'type': 'paragraph', 'text': ...}
      {'type': 'table', 'num_cols': N, 'grid': [[cell|None, ...], ...]}
        where cell is {'text': ..., 'colspan': N, 'rowspan': M}
    """
    start_targets = [start_headings] if isinstance(start_headings, str) else start_headings
    start_be_idx = None
    for i, be in enumerate(body_elements):
        if be['type'] == 'p' and _is_heading(be['text'], start_targets):
            start_be_idx = i
            break
    if start_be_idx is None:
        return []

    end_be_idx = len(body_elements)
    for i in range(start_be_idx + 1, len(body_elements)):
        be = body_elements[i]
        if be['type'] == 'p' and _is_heading(be['text'], end_headings):
            end_be_idx = i
            break

    blocks = []
    for i in range(start_be_idx + 1, end_be_idx):
        be = body_elements[i]
        if be['type'] == 'p':
            if be['text']:
                blocks.append({'type': 'paragraph', 'text': be['text']})
        elif be['type'] == 't':
            blocks.append({
                'type': 'table',
                'num_cols': be['num_cols'],
                'grid': be['grid'],
            })
    return blocks


def extract_syllabus_fields(paragraphs, tables, tables_rich=None, body_elements=None):
    """Extract structured syllabus fields from parsed .docx content.

    Combines:
    1. Rich table KV extraction (ALL fields including checkbox states)
    2. Labeled paragraph extraction (fallback for non-table fields)
    3. Section-based content extraction (课程目标, 教材, 评价标准)

    Returns a dict with keys matching the report template fields.
    """
    # 1. Rich table extraction — capture ALL key-value pairs including checkboxes
    fields = {}
    if tables_rich:
        all_kv = _extract_all_table_kv(tables_rich)
        # Map known labels to canonical field names
        for label, key in SIMPLE_FIELD_LABELS.items():
            # Try exact match on the full key
            for kv_key, value in all_kv.items():
                norm_kv_key = _normalize(kv_key)
                norm_label = _normalize(label)
                if norm_kv_key == norm_label or norm_kv_key.startswith(norm_label) or norm_label in norm_kv_key:
                    if key not in fields and value.strip():
                        fields[key] = value.strip()
                        break

        # Store ALL raw table KV pairs for report generation use
        fields['_all_table_kv'] = all_kv

    # 2. Simple fields from labeled paragraphs (fill gaps not found in tables)
    for p in paragraphs:
        text = p['text'].strip()
        for label, key in SIMPLE_FIELD_LABELS.items():
            if key in fields:
                continue
            m = re.match(re.escape(label) + r'\s*[：:]\s*(.+)', text)
            if m:
                val = m.group(1).strip()
                if val:
                    fields[key] = val
                break

    # 3. 课程目标
    start, end = _find_section_range(
        paragraphs, ['课程目标', '教学目标'], SECTION_HEADINGS)
    if start is not None:
        texts = []
        for i in range(start + 1, end):
            t = paragraphs[i]['text'].strip()
            if t:
                texts.append(t)
        # Strip trailing table guide paragraphs
        while texts and _is_table_guide(texts[-1]):
            texts.pop()
        if texts:
            fields['course_objectives'] = '\n'.join(texts)

    # 4. 选用教材
    textbook_start, textbook_end = _find_section_range(
        paragraphs, '课程教材', SECTION_HEADINGS)
    if textbook_start is not None:
        ref_start, _ = _find_section_range(
            paragraphs, ['参考教材及网站', '参考教材与网站'], [])
        effective_end = ref_start if ref_start is not None else textbook_end
        texts = []
        for i in range(textbook_start + 1, effective_end):
            t = paragraphs[i]['text'].strip()
            if t:
                texts.append(t)
        if texts:
            fields['textbook'] = '\n'.join(texts)

    # 5. 课程考核及成绩评定 — extract as blocks (paragraphs + tables)
    eval_headings = ['课程考核及成绩评定', '课程考核与成绩评定', '考核及成绩评定', '考核与成绩评定']
    if body_elements:
        blocks = _extract_section_blocks(
            body_elements, eval_headings, SECTION_HEADINGS)
        if blocks:
            fields['evaluation_standards'] = blocks
    else:
        # Fallback: body_elements not available, use paragraphs only
        eval_start, eval_end = _find_section_range(paragraphs, eval_headings, SECTION_HEADINGS)
        if eval_start is not None:
            texts = []
            for i in range(eval_start + 1, eval_end):
                t = paragraphs[i]['text'].strip()
                if t:
                    texts.append(t)
            if texts:
                fields['evaluation_standards'] = '\n'.join(texts)

    # 6. Fill defaults
    all_keys = (
        list(SIMPLE_FIELD_LABELS.values())
        + ['course_objectives', 'textbook', 'evaluation_standards']
    )
    for k in all_keys:
        if k not in fields:
            fields[k] = '未填写'

    return fields
