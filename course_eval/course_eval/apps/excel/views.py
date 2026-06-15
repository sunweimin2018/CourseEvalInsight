import os
import pickle
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from course_eval.utils.response import api_response
from .serializers import ExcelUploadSerializer
from .validators import validate_file_extension, validate_file_size, validate_file_count
from .parser import parse_excel
from .cleaner import clean_and_fuse


def _cache_key(user_id, suffix):
    return f'excel_{user_id}_{suffix}'


class ExcelUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        files = request.FILES.getlist('files')
        if not files:
            return api_response(code=400, msg='No files provided', http_status=400)
        validate_file_count(files)

        parsed_data = {}
        total_rows = 0
        sheets_parsed = []
        excel_files = []

        upload_dir = os.path.join(
            settings.MEDIA_ROOT, 'uploads', request.user.username,
            datetime.now().strftime('%Y%m%d_%H%M%S'),
        )
        os.makedirs(upload_dir, exist_ok=True)

        for f in files:
            validate_file_extension(f.name)
            validate_file_size(f.size)

            file_path = os.path.join(upload_dir, f.name)
            with open(file_path, 'wb+') as dest:
                for chunk in f.chunks():
                    dest.write(chunk)

            from .models import ExcelFile
            ef = ExcelFile.objects.create(
                file_name=f.name,
                file_path=os.path.relpath(file_path, settings.MEDIA_ROOT),
                file_size=f.size,
                user=request.user,
            )
            excel_files.append({'id': ef.id, 'file_name': ef.file_name})

            try:
                sheets = parse_excel(file_path)
                parsed_data[f.name] = sheets
                for sheet_name, content in sheets.items():
                    sheets_parsed.append(f'{f.name}/{sheet_name}')
                    total_rows += len(content['rows'])
            except Exception as e:
                return api_response(
                    code=400,
                    msg=f'Failed to parse "{f.name}": {str(e)}',
                    http_status=400,
                )

        cache.set(_cache_key(request.user.id, 'parsed'), pickle.dumps(parsed_data), timeout=3600)

        return api_response(data={
            'total_files': len(files),
            'total_rows': total_rows,
            'sheets_parsed': sheets_parsed,
            'files': excel_files,
        })


class RawDataView(APIView):
    def get(self, request):
        cached = cache.get(_cache_key(request.user.id, 'parsed'))
        if not cached:
            return api_response(code=404, msg='No uploaded data found', http_status=404)

        parsed_data = pickle.loads(cached)
        all_rows = []
        headers = []
        for _file_name, sheets in parsed_data.items():
            for _sheet_name, content in sheets.items():
                for row in content['rows']:
                    all_rows.append(row)
                if not headers:
                    headers = content['headers']

        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 20))
        paginator = Paginator(all_rows, size)
        page_obj = paginator.get_page(page)

        return api_response(data={
            'headers': headers,
            'rows': list(page_obj.object_list),
            'total': paginator.count,
            'page': page,
            'page_size': size,
        })


class CleanDataView(APIView):
    def post(self, request):
        cached = cache.get(_cache_key(request.user.id, 'parsed'))
        if not cached:
            return api_response(code=404, msg='No uploaded data found', http_status=404)

        parsed_data = pickle.loads(cached)
        cleaned, summary = clean_and_fuse(parsed_data)
        cache.set(_cache_key(request.user.id, 'cleaned'), pickle.dumps(cleaned), timeout=3600)
        cache.set(_cache_key(request.user.id, 'cleaning_summary'), pickle.dumps(summary), timeout=3600)

        return api_response(data=summary)


class CleanedDataPreviewView(APIView):
    def get(self, request):
        cached = cache.get(_cache_key(request.user.id, 'cleaned'))
        if not cached:
            return api_response(code=404, msg='No cleaned data found', http_status=404)

        cleaned = pickle.loads(cached)
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 20))
        paginator = Paginator(cleaned['rows'], size)
        page_obj = paginator.get_page(page)

        return api_response(data={
            'headers': cleaned['headers'],
            'rows': list(page_obj.object_list),
            'total': paginator.count,
            'page': page,
            'page_size': size,
        })
