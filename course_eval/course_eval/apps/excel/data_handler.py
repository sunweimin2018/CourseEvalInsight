import os
import pickle

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator

from .parser import parse_excel
from .models import CourseFileRecord, WorkbookSnapshot


def _cache_key(user_id, file_record_id):
    return f'working_copy_{user_id}_{file_record_id}'


def _check_excel(file_record):
    ext = os.path.splitext(file_record.file_name)[1].lower()
    if ext not in ('.xlsx', '.xls'):
        raise ValueError('仅支持 Excel 文件')
    return ext


def open_working_copy(file_record, user_id):
    """Parse the original Excel file and create a working copy in cache."""
    _check_excel(file_record)
    full_path = os.path.join(settings.MEDIA_ROOT, file_record.file_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError('原始文件不存在')

    sheets = parse_excel(full_path)
    first_sheet_name = list(sheets.keys())[0]
    sheet_data = sheets[first_sheet_name]
    sheet_data['sheet_name'] = first_sheet_name

    cache.set(_cache_key(user_id, file_record.id), pickle.dumps(sheet_data), timeout=7200)
    return sheet_data


def get_working_data(file_record, user_id, page=1, size=20):
    """Get paginated data from the working copy."""
    _check_excel(file_record)
    key = _cache_key(user_id, file_record.id)
    cached = cache.get(key)

    if cached is None:
        raise FileNotFoundError('工作副本不存在，请先打开文件')

    data = pickle.loads(cached)
    paginator = Paginator(data['rows'], size)
    page_obj = paginator.get_page(page)

    return {
        'sheet_name': data.get('sheet_name', 'Sheet1'),
        'headers': data['headers'],
        'rows': list(page_obj.object_list),
        'total': paginator.count,
        'page': page,
        'page_size': size,
    }


def _touch_cache(file_record, user_id, data):
    cache.set(_cache_key(user_id, file_record.id), pickle.dumps(data), timeout=7200)


def add_row(file_record, user_id, row_data):
    """Append a new row to the working copy."""
    key = _cache_key(user_id, file_record.id)
    cached = cache.get(key)
    if cached is None:
        raise FileNotFoundError('工作副本不存在，请先打开文件')

    data = pickle.loads(cached)
    new_row = {}
    for h in data['headers']:
        new_row[h] = row_data.get(h, '')
    data['rows'].append(new_row)
    _touch_cache(file_record, user_id, data)
    return {'row': new_row, 'total_rows': len(data['rows'])}


def update_cell(file_record, user_id, row_idx, col_name, value):
    """Update a single cell in the working copy."""
    key = _cache_key(user_id, file_record.id)
    cached = cache.get(key)
    if cached is None:
        raise FileNotFoundError('工作副本不存在，请先打开文件')

    data = pickle.loads(cached)
    if row_idx < 0 or row_idx >= len(data['rows']):
        raise IndexError('行索引超出范围')
    if col_name not in data['headers']:
        raise ValueError(f'列名 "{col_name}" 不存在')

    data['rows'][row_idx][col_name] = value
    _touch_cache(file_record, user_id, data)
    return {'row_idx': row_idx, 'col_name': col_name, 'value': value}


def delete_row(file_record, user_id, row_idx):
    """Delete a row from the working copy."""
    key = _cache_key(user_id, file_record.id)
    cached = cache.get(key)
    if cached is None:
        raise FileNotFoundError('工作副本不存在，请先打开文件')

    data = pickle.loads(cached)
    if row_idx < 0 or row_idx >= len(data['rows']):
        raise IndexError('行索引超出范围')

    data['rows'].pop(row_idx)
    _touch_cache(file_record, user_id, data)
    return {'deleted_index': row_idx, 'total_rows': len(data['rows'])}


def save_snapshot(file_record, user_id):
    """Persist the working copy to a WorkbookSnapshot record."""
    key = _cache_key(user_id, file_record.id)
    cached = cache.get(key)
    if cached is None:
        raise FileNotFoundError('工作副本不存在，请先打开文件')

    data = pickle.loads(cached)
    rows = data['rows']

    WorkbookSnapshot.objects.filter(
        source_file=file_record, is_latest=True
    ).update(is_latest=False)

    snapshot = WorkbookSnapshot.objects.create(
        source_file=file_record,
        user_id=user_id,
        headers=data['headers'],
        rows=rows,
        row_count=len(rows),
        is_latest=True,
    )
    return {'snapshot_id': snapshot.id, 'row_count': snapshot.row_count}


def reset_working_copy(file_record, user_id):
    """Discard the working copy and re-parse the original file."""
    key = _cache_key(user_id, file_record.id)
    cache.delete(key)
    return open_working_copy(file_record, user_id)


def get_effective_data(file_record, user_id):
    """
    Get the effective data for a file — returns the latest saved snapshot if it exists,
    otherwise parses the original file. Used by report generation.
    """
    snapshot = WorkbookSnapshot.objects.filter(
        source_file=file_record, is_latest=True
    ).first()

    if snapshot:
        return {
            'headers': snapshot.headers,
            'rows': snapshot.rows,
            'total': snapshot.row_count,
        }

    full_path = os.path.join(settings.MEDIA_ROOT, file_record.file_path)
    sheets = parse_excel(full_path)
    first_sheet_name = list(sheets.keys())[0]
    sheet_data = sheets[first_sheet_name]
    return {
        'headers': sheet_data['headers'],
        'rows': sheet_data['rows'],
        'total': len(sheet_data['rows']),
    }
