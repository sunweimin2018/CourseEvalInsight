import os
import pickle
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from course_eval.utils.response import api_response
from .models import Course, ClassGroup, Semester, CourseFileRecord
from .serializers import (
    ExcelUploadSerializer, CourseSerializer, ClassGroupSerializer,
    SemesterSerializer, CourseFileRecordSerializer, CourseFileUploadSerializer,
)
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


# ── Course / ClassGroup / Semester ──────────────────────────────────────────

class BaseUserListCreateView(APIView):
    model = None
    serializer_class = None

    def get(self, request):
        qs = self.model.objects.filter(user=request.user)
        ser = self.serializer_class(qs, many=True)
        return api_response(data=ser.data)

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return api_response(code=400, msg='名称不能为空', http_status=400)
        obj, created = self.model.objects.get_or_create(
            name=name, user=request.user,
        )
        ser = self.serializer_class(obj)
        return api_response(data=ser.data, msg='创建成功' if created else '已存在，已自动选择')


class CourseListView(BaseUserListCreateView):
    model = Course
    serializer_class = CourseSerializer


class ClassGroupListView(BaseUserListCreateView):
    model = ClassGroup
    serializer_class = ClassGroupSerializer


class SemesterListView(BaseUserListCreateView):
    model = Semester
    serializer_class = SemesterSerializer


# ── Course files ────────────────────────────────────────────────────────────

class CourseFileUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        ser = CourseFileUploadSerializer(data=request.data)
        if not ser.is_valid():
            return api_response(code=400, msg=ser.errors, http_status=400)

        data = ser.validated_data
        course = get_object_or_404(Course, id=data['course_id'], user=request.user)
        class_group = get_object_or_404(ClassGroup, id=data['class_id'], user=request.user)
        semester = get_object_or_404(Semester, id=data['semester_id'], user=request.user)

        f = data['file']
        validate_file_extension(f.name, file_type=data['file_type'])
        validate_file_size(f.size)

        upload_dir = os.path.join(
            settings.MEDIA_ROOT, 'course_files',
            request.user.username,
            str(course.id), str(class_group.id), str(semester.id),
        )
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f.name)
        with open(file_path, 'wb+') as dest:
            for chunk in f.chunks():
                dest.write(chunk)

        record, created = CourseFileRecord.objects.update_or_create(
            course=course,
            class_group=class_group,
            semester=semester,
            file_type=data['file_type'],
            user=request.user,
            defaults={
                'file_name': f.name,
                'file_path': os.path.relpath(file_path, settings.MEDIA_ROOT),
                'file_size': f.size,
            },
        )

        out = CourseFileRecordSerializer(record).data
        return api_response(data=out, msg='覆盖上传成功' if not created else '上传成功')


class CourseFileListView(APIView):
    def get(self, request):
        course_id = request.query_params.get('course_id')
        class_id = request.query_params.get('class_id')
        semester_id = request.query_params.get('semester_id')
        if not all([course_id, class_id, semester_id]):
            return api_response(code=400, msg='请提供 course_id, class_id, semester_id', http_status=400)

        qs = CourseFileRecord.objects.filter(
            user=request.user,
            course_id=course_id,
            class_group_id=class_id,
            semester_id=semester_id,
        )
        ser = CourseFileRecordSerializer(qs, many=True)
        return api_response(data=ser.data)


class CourseFileDeleteView(APIView):
    def delete(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        full_path = os.path.join(settings.MEDIA_ROOT, record.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        record.delete()
        return api_response(msg='删除成功')
