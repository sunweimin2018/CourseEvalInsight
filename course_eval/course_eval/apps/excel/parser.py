import math
import os
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

        # Detect merged-title pattern: few named columns + first row looks like real headers
        unnamed_count = sum(1 for h in headers if h.startswith('Unnamed:'))
        if unnamed_count >= len(headers) * 0.5 and rows and _looks_like_header_row(rows[0].values()):
            first_row = rows[0]
            new_headers = [str(first_row[k]).replace(' ', '').replace('\n', '') for k in first_row]
            # Remap remaining rows to use new header keys
            remapped = []
            for old_row in rows[1:]:
                remapped.append({new_headers[i]: v for i, (_, v) in enumerate(old_row.items())})
            headers = new_headers
            rows = remapped

        sheets[sheet_name] = {
            'headers': headers,
            'rows': _sanitize_rows(rows),
        }
    return sheets
