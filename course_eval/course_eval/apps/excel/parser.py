import math
import os
import re
import pandas as pd


# Sub-header row detection: when the first row looks like a merged title,
# promote the first data row to column headers.
KNOWN_HEADER_LABELS = {'学号', '姓名', '性别', '班级', '院系', '专业', '年级',
                       '成绩', '分数', '课程', '教师', '学期', '课序号',
                       '课程编号', '课程名称', '学分', '学时', '考试方式',
                       '选课类型', '备注', '是否缓考', '修读方式', '课程性质',
                       '课程类型', '教材', '编号', '序号', '学号/证号',
                       '得分', '总评', '平时', '期末', '实验', '作业',
                       '考勤', '评价', '等级', '考核方式', '教师姓名',
                       '开课院系', '上课班级', '学生证号', '学号姓名'}


def _sanitize_value(v):
    """Convert numpy/NaN values to JSON-safe Python types."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, float) and math.isinf(v):
        return None
    if hasattr(v, 'item'):  # numpy scalar
        return v.item()
    return v


def _sanitize_rows(rows):
    """Ensure all cell values are JSON-serializable."""
    return [{k: _sanitize_value(v) for k, v in row.items()} for row in rows]


def _dedup_headers(headers):
    """Fill empty header names and deduplicate by appending numeric suffixes."""
    seen: dict[str, int] = {}
    result = []
    for h in headers:
        h = str(h).strip()
        if not h:
            h = f'列_{len(result) + 1}'
        if h in seen:
            seen[h] += 1
            result.append(f'{h}_{seen[h]}')
        else:
            seen[h] = 0
            result.append(h)
    return result


def _looks_like_header_row(row_values):
    """Return True if a majority of non-empty cell values look like column headers."""
    hits = 0
    total = 0
    for v in row_values:
        s = str(v).replace(' ', '').replace('\n', '').strip()
        if not s or s == 'None' or s == 'nan':
            continue
        total += 1
        if s in KNOWN_HEADER_LABELS:
            hits += 1
        elif any(label in s for label in KNOWN_HEADER_LABELS):
            hits += 1
    return total > 0 and hits >= total * 0.5


def _parse_title_text(text):
    """Parse a title cell to extract course_code, course_name, course_seq.

    Handles two formats:
      Labeled:   课程编号=B13050100  课程名称=大学计算机  课序号=01
      Unlabeled: B13050100  大学计算机（课序号=01）
    """
    if not text or text in ('None', 'nan', 'null', 'NaN'):
        return None

    result = {}

    # Always try to extract 课序号 via regex.
    # \S+ captures non-whitespace; [）)]? explicitly includes a trailing closing
    # parenthesis that may be separated by zero-width boundary from the digits.
    seq_match = re.search(r'课序号[=：:]\s*(\S+[）)]?)', text)
    if seq_match:
        result['course_seq'] = seq_match.group(1).strip().rstrip(')）')

    # Try labeled format first
    code_match = re.search(r'课程编号[=：:]\s*(\S+)', text)
    name_match = re.search(r'课程名称[=：:]\s*(.+?)(?=\s*(?:课程|课序|$))', text)

    if code_match:
        result['course_code'] = code_match.group(1).strip()
    if name_match:
        result['course_name'] = name_match.group(1).strip()

    # If labeled format didn't yield course_code/course_name, try unlabeled
    if 'course_code' not in result or 'course_name' not in result:
        # Remove 课序号=XX (and surrounding parentheses) to isolate code + name
        remaining = re.sub(r'[（(]?\s*课序号[=：:]\s*\S+\s*[）)]?', '', text).strip()
        # Also remove 课程编号=, 课程名称= labels if present
        remaining = re.sub(r'课程(?:编号|名称)[=：:]\s*\S+', '', remaining).strip()

        parts = remaining.split(None, 2)  # split on whitespace, max 2 parts
        if 'course_code' not in result and parts:
            result['course_code'] = parts[0].strip()
        if 'course_name' not in result and len(parts) > 1:
            name = parts[1].strip()
            name = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
            if name:
                result['course_name'] = name

    return result if result else None


def _extract_title_metadata(headers, rows):
    """Extract course metadata from grade Excel title row.

    Searches headers and first data row for course info patterns.
    Merges results across all candidates so partial matches (e.g. course_code
    in one cell, course_seq in another) are combined.
    """
    candidates = []
    for h in headers:
        s = str(h).strip()
        if s and s not in ('None', 'nan', 'null'):
            candidates.append(s)
    if rows:
        for v in rows[0].values():
            s = str(v).strip() if v else ''
            if s and s not in ('None', 'nan', 'null'):
                candidates.append(s)

    merged = {}
    for text in candidates:
        result = _parse_title_text(text)
        if result:
            for k, v in result.items():
                if v and k not in merged:
                    merged[k] = v
    return merged if merged else None


def parse_excel(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.xls':
        engine = 'calamine'
    elif ext == '.xlsx':
        engine = 'calamine'
    else:
        raise ValueError(f'不支持的文件格式: {ext}')

    sheets = {}
    xl = pd.ExcelFile(file_path, engine=engine)
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)
        df = df.where(pd.notnull(df), None)

        headers = list(df.columns.astype(str))
        rows = df.to_dict(orient='records')

        # Extract course metadata from the title row before promotion
        metadata = _extract_title_metadata(headers, rows)

        # Detect merged-title pattern: when most columns are unnamed, try to
        # promote data rows that look like real headers.  Loop to handle
        # multi-level headers (e.g. merged title → category → sub-headers).
        unnamed_count = sum(1 for h in headers if h.startswith('Unnamed:'))
        depth = 0
        while unnamed_count >= len(headers) * 0.5 and rows and depth < 3:
            if not _looks_like_header_row(rows[0].values()):
                break
            first_row = rows[0]
            new_headers = [str(first_row[k]).replace(' ', '').replace('\n', '') for k in first_row]
            new_headers = _dedup_headers(new_headers)
            remapped = []
            for old_row in rows[1:]:
                remapped.append({new_headers[i]: v for i, (_, v) in enumerate(old_row.items())})
            headers = new_headers
            rows = remapped
            depth += 1
            unnamed_count = sum(1 for h in headers if h.startswith('Unnamed:'))

        sheets[sheet_name] = {
            'headers': headers,
            'rows': _sanitize_rows(rows),
            'metadata': metadata,
        }
    return sheets
