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
from .word_parser import parse_docx, extract_syllabus_fields
from . import data_handler
from . import validation as upload_validation
from . import grades_template


GRADE_KEYWORDS = {'成绩', '分数', '得分', '总评', '平时', '期末', '实验', '作业',
                  '考勤', '评价', '等级', '考核', '测试', '考试', '期中', '报告'}


def _check_upload_headers(file_path, file_type):
    """Parse the uploaded file and return header warnings if any."""
    warnings = []
    try:
        sheets = parse_excel(file_path)
        first_sheet = list(sheets.values())[0]
        headers = first_sheet['headers']
    except Exception:
        return warnings

    has_name = any('姓名' in h for h in headers)
    has_student_id = any('学号' in h for h in headers)

    if file_type == 'student_info':
        if not has_name:
            warnings.append('缺少"姓名"列')
        if not has_student_id:
            warnings.append('未找到"学号"列')
    elif file_type == 'grades':
        if not has_name:
            warnings.append('缺少"姓名"列')
        has_grade_col = any(
            any(kw in h for kw in GRADE_KEYWORDS) for h in headers
        )
        if not has_grade_col:
            warnings.append('未检测到成绩相关列')

    return warnings


def _cache_key(user_id, suffix):
    return f'excel_{user_id}_{suffix}'


def _get_course_params(data):
    """Extract and validate course_id, class_id, semester_name from data dict."""
    course_id = data.get('course_id')
    class_id = data.get('class_id')
    semester_name = data.get('semester_name')
    if not all([course_id, class_id, semester_name]):
        return None, api_response(code=400, msg='参数不完整', http_status=400)
    return (course_id, class_id, semester_name), None


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
    # Subclasses set this to the field name on CourseFileRecord that links to this model
    _file_record_field = None

    def _apply_association_filters(self, qs, request):
        """Filter qs to only items that have CourseFileRecord associations matching the params."""
        file_qs = CourseFileRecord.objects.filter(user=request.user)

        course_id = request.query_params.get('course_id')
        class_id = request.query_params.get('class_id')
        semester_name = request.query_params.get('semester_name')

        if not any([course_id, class_id, semester_name]):
            return qs

        if course_id:
            file_qs = file_qs.filter(course_id=course_id)
        if class_id:
            file_qs = file_qs.filter(class_group_id=class_id)
        if semester_name:
            semester = Semester.objects.filter(name=semester_name, user=request.user).first()
            if semester:
                file_qs = file_qs.filter(semester=semester)
            else:
                return qs.none()

        linked_ids = file_qs.values_list(self._file_record_field, flat=True).distinct()
        return qs.filter(id__in=linked_ids)

    def get(self, request):
        qs = self.model.objects.filter(user=request.user)
        qs = self._apply_association_filters(qs, request)
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
    _file_record_field = 'course_id'


class ClassGroupListView(BaseUserListCreateView):
    model = ClassGroup
    serializer_class = ClassGroupSerializer
    _file_record_field = 'class_group_id'


class SemesterListView(BaseUserListCreateView):
    model = Semester
    serializer_class = SemesterSerializer
    _file_record_field = 'semester_id'


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
        semester, _ = Semester.objects.get_or_create(
            name=data['semester_name'], user=request.user,
        )

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

        # Reset validation status for all files in this group
        CourseFileRecord.objects.filter(
            course=course, class_group=class_group,
            semester=semester, user=request.user,
        ).update(validation_status='pending')

        header_warnings = _check_upload_headers(file_path, data['file_type'])

        # Extract course metadata from the uploaded file's title row
        try:
            sheets = parse_excel(file_path)
            first_sheet = list(sheets.values())[0] if sheets else {}
            file_metadata = first_sheet.get('metadata')
            if file_metadata:
                record.title_metadata = file_metadata
                record.save(update_fields=['title_metadata'])
        except Exception:
            file_metadata = None

        out = CourseFileRecordSerializer(record).data
        out['header_warnings'] = header_warnings
        return api_response(data=out, msg='覆盖上传成功' if not created else '上传成功')


class CourseFileListView(APIView):
    def get(self, request):
        course_id = request.query_params.get('course_id')
        class_id = request.query_params.get('class_id')
        semester_name = request.query_params.get('semester_name')
        if not all([course_id, class_id, semester_name]):
            return api_response(code=400, msg='请提供 course_id, class_id, semester_name', http_status=400)

        semester = Semester.objects.filter(name=semester_name, user=request.user).first()
        if not semester:
            return api_response(data=[])

        qs = CourseFileRecord.objects.filter(
            user=request.user,
            course_id=course_id,
            class_group_id=class_id,
            semester_id=semester.id,
        )
        ser = CourseFileRecordSerializer(qs, many=True)
        return api_response(data=ser.data)


class CourseFileDeleteView(APIView):
    def delete(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)

        # Cascade: deleting syllabus also removes student_info and grades;
        # deleting student_info also removes grades.
        cascade_types = []
        if record.file_type == 'syllabus':
            cascade_types = ['student_info', 'grades']
        elif record.file_type == 'student_info':
            cascade_types = ['grades']

        if cascade_types:
            downstream = CourseFileRecord.objects.filter(
                course=record.course,
                class_group=record.class_group,
                semester=record.semester,
                user=request.user,
                file_type__in=cascade_types,
            )
            for dr in downstream:
                dr_path = os.path.join(settings.MEDIA_ROOT, dr.file_path)
                if os.path.exists(dr_path):
                    os.remove(dr_path)
                dr.delete()

        full_path = os.path.join(settings.MEDIA_ROOT, record.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        record.delete()

        # Reset validation status on remaining files
        remaining = CourseFileRecord.objects.filter(
            course=record.course,
            class_group=record.class_group,
            semester=record.semester,
            user=request.user,
        )
        if remaining.exists():
            remaining.update(validation_status='pending')

        return api_response(msg='删除成功')


# ── Data Preview – Word content ──────────────────────────────────────────────

class WordContentView(APIView):
    def get(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        if record.file_type != 'syllabus':
            return api_response(code=400, msg='仅课程大纲文件支持此操作', http_status=400)

        full_path = os.path.join(settings.MEDIA_ROOT, record.file_path)
        if not os.path.exists(full_path):
            return api_response(code=404, msg='文件不存在', http_status=404)

        result = parse_docx(full_path)
        if 'error' in result:
            return api_response(code=400, msg=result['error'], http_status=400)

        fields = extract_syllabus_fields(
            result['paragraphs'], result['tables'],
            tables_rich=result.get('_tables_rich'),
            body_elements=result.get('_body_elements'),
        )

        # Don't expose internal _tables_rich via API
        out = {
            'paragraphs': result['paragraphs'],
            'tables': result['tables'],
            'body_elements': result.get('body_elements', []),
            'file_name': record.file_name,
            'fields': fields,
        }
        return api_response(data=out)


# ── Data Preview – Excel working copy CRUD ──────────────────────────────────

class OpenWorkingCopyView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        try:
            data = data_handler.open_working_copy(record, request.user.id)
        except (ValueError, FileNotFoundError) as e:
            return api_response(code=400, msg=str(e), http_status=400)

        return api_response(data={
            'sheet_name': data['sheet_name'],
            'headers': data['headers'],
            'rows': data['rows'],
            'total': len(data['rows']),
            'page': 1,
            'page_size': len(data['rows']),
        })


class WorkingDataView(APIView):
    def get(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 20))

        try:
            data = data_handler.get_working_data(record, request.user.id, page, size)
        except FileNotFoundError:
            return api_response(code=400, msg='请先打开文件', http_status=400)
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)

        return api_response(data=data)


class AddRowView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        try:
            result = data_handler.add_row(record, request.user.id, request.data)
        except FileNotFoundError:
            return api_response(code=400, msg='请先打开文件', http_status=400)

        return api_response(data=result, msg='新增成功')


class UpdateCellView(APIView):
    def put(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        row_idx = request.data.get('row_idx')
        col_name = request.data.get('col_name')
        value = request.data.get('value')

        if row_idx is None or col_name is None:
            return api_response(code=400, msg='请提供 row_idx 和 col_name', http_status=400)

        try:
            result = data_handler.update_cell(
                record, request.user.id, int(row_idx), col_name, value
            )
        except (FileNotFoundError, IndexError, ValueError) as e:
            return api_response(code=400, msg=str(e), http_status=400)

        return api_response(data=result)


class DeleteRowView(APIView):
    def delete(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        row_idx = request.data.get('row_idx')
        if row_idx is None:
            return api_response(code=400, msg='请提供 row_idx', http_status=400)

        try:
            result = data_handler.delete_row(record, request.user.id, int(row_idx))
        except (FileNotFoundError, IndexError) as e:
            return api_response(code=400, msg=str(e), http_status=400)

        return api_response(data=result, msg='删除成功')


class SaveSnapshotView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        try:
            result = data_handler.save_snapshot(record, request.user.id)
        except FileNotFoundError:
            return api_response(code=400, msg='请先打开文件', http_status=400)

        return api_response(data=result, msg='保存成功')


class ResetWorkingCopyView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        try:
            data = data_handler.reset_working_copy(record, request.user.id)
        except (ValueError, FileNotFoundError) as e:
            return api_response(code=400, msg=str(e), http_status=400)

        return api_response(data={
            'sheet_name': data['sheet_name'],
            'headers': data['headers'],
            'rows': data['rows'],
            'total': len(data['rows']),
        }, msg='已重置为原始数据')


# ── Exam status analysis ──────────────────────────────────────────────────────

class ExamStatusAnalysisView(APIView):
    def post(self, request):
        params, err = _get_course_params(request.data)
        if err:
            return err
        course_id, class_id, semester_name = params
        try:
            result = upload_validation.analyze_exam_status(
                request.user, course_id, class_id, semester_name,
            )
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)
        except Exception as e:
            return api_response(code=500, msg=f'分析过程出错：{e}', http_status=500)
        return api_response(data=result)


# ── Upload validation ─────────────────────────────────────────────────────────

class GradesValidationView(APIView):
    def post(self, request):
        params, err = _get_course_params(request.data)
        if err:
            return err
        course_id, class_id, semester_name = params
        try:
            result = upload_validation.validate_grades_upload(
                request.user, course_id, class_id, semester_name,
            )
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)
        except Exception as e:
            return api_response(code=500, msg=f'验证过程出错：{e}', http_status=500)
        return api_response(data=result)


class CountMismatchResolveView(APIView):
    def post(self, request):
        course_id = request.data.get('course_id')
        class_id = request.data.get('class_id')
        semester_name = request.data.get('semester_name')
        user_choice = request.data.get('user_choice')
        if not all([course_id, class_id, semester_name, user_choice]):
            return api_response(code=400, msg='参数不完整', http_status=400)
        if user_choice not in ('student_info_wrong', 'grades_wrong'):
            return api_response(code=400, msg='无效的选择', http_status=400)
        try:
            deleted = upload_validation.resolve_count_mismatch(
                request.user, course_id, class_id, semester_name, user_choice,
            )
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)
        except Exception as e:
            return api_response(code=500, msg=f'处理出错：{e}', http_status=500)
        return api_response(data={'deleted': deleted}, msg='处理成功')


class FixHeadersView(APIView):
    def post(self, request, pk):
        record = get_object_or_404(CourseFileRecord, id=pk, user=request.user)
        mapping = request.data.get('mapping', {})
        if not mapping:
            return api_response(code=400, msg='请提供 header mapping', http_status=400)
        try:
            new_headers = upload_validation.fix_grades_headers(record, request.user.id, mapping)
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)
        except Exception as e:
            return api_response(code=500, msg=f'修复表头出错：{e}', http_status=500)
        return api_response(data={'headers': new_headers}, msg='表头更新成功')


class ForcePassValidationView(APIView):
    def post(self, request):
        params, err = _get_course_params(request.data)
        if err:
            return err
        course_id, class_id, semester_name = params

        semester = Semester.objects.filter(name=semester_name, user=request.user).first()
        if not semester:
            return api_response(code=400, msg='学期不存在', http_status=400)

        upload_validation._set_file_validation_status(
            request.user, course_id, class_id, semester, 'syllabus', 'passed')
        upload_validation._set_file_validation_status(
            request.user, course_id, class_id, semester, 'student_info', 'passed')
        upload_validation._set_file_validation_status(
            request.user, course_id, class_id, semester, 'grades', 'passed')

        return api_response(msg='验证状态已更新')


# ── Grades template download ───────────────────────────────────────────────────

class GradesTemplateView(APIView):
    def get(self, request):
        params, err = _get_course_params(request.query_params)
        if err:
            return err
        course_id, class_id, semester_name = params
        try:
            return grades_template.generate_grades_template(
                request.user, course_id, class_id, semester_name,
            )
        except ValueError as e:
            return api_response(code=400, msg=str(e), http_status=400)
        except Exception as e:
            return api_response(code=500, msg=f'生成模板出错：{e}', http_status=500)
