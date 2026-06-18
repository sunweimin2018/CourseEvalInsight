from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from course_eval.utils.response import api_response
from .models import ReportRecord
from .serializers import ReportRecordSerializer, ReportGenerateSerializer
from .report_engine import generate_report


class ReportGenerateView(APIView):
    def post(self, request):
        serializer = ReportGenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(code=400, msg='参数错误', data=serializer.errors, http_status=400)

        data = serializer.validated_data
        user_id = request.user.id

        result = generate_report(
            user_id, data['course_id'], data['class_id'], data['semester_name']
        )

        # Upsert — one report per course/class/semester/user
        report, _ = ReportRecord.objects.update_or_create(
            course=result['course'],
            class_group=result['class_group'],
            semester=result['semester'],
            user=request.user,
            defaults={
                'report_name': result['report_name'],
                'report_data': result['report_data'],
                'syllabus_file': result['syllabus_file'],
                'student_info_file': result['student_info_file'],
                'grades_file': result['grades_file'],
                'status': 'completed',
            },
        )

        return api_response(data=ReportRecordSerializer(report).data)


class ReportPreviewView(APIView):
    def get(self, request, pk):
        report = ReportRecord.objects.filter(id=pk, user=request.user).first()
        if not report:
            return api_response(code=404, msg='报告不存在', http_status=404)

        return api_response(data={
            **ReportRecordSerializer(report).data,
            'report_data': report.report_data,
        })


class ReportExportView(APIView):
    def get(self, request, pk):
        from django.http import FileResponse
        from docx import Document
        from docx.shared import Inches, Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        report = ReportRecord.objects.filter(id=pk, user=request.user).first()
        if not report:
            return api_response(code=404, msg='报告不存在', http_status=404)

        rd = report.report_data
        doc = Document()

        # Title
        title = doc.add_heading(report.report_name, level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # ── Module 1: Course Basic Info Table ──────────────────────────────
        doc.add_heading('一、课程基本信息表', level=1)
        info = rd.get('module_1_course_info', {})
        table = doc.add_table(rows=6, cols=4, style='Table Grid')
        cells = [
            ['课程名称：', info.get('course_name', ''), '修课人数：', str(info.get('student_count', ''))],
            ['课程编号：', info.get('course_code', ''), '课序号：', str(info.get('course_seq', ''))],
            ['授课班级：', info.get('teaching_class', ''), '学时数：', str(info.get('total_hours', ''))],
            ['选用教材：', info.get('textbook', ''), '学分：', str(info.get('credits', ''))],
            ['开课院系：', info.get('department', ''), '授课教师：', str(info.get('teacher', ''))],
            ['课程性质：', info.get('course_nature', ''), '课程类型：', str(info.get('course_type', ''))],
        ]
        for r_idx, row_cells in enumerate(cells):
            for c_idx, text in enumerate(row_cells):
                cell = table.cell(r_idx, c_idx)
                cell.text = text

        # ── Module 2: Course Objectives ────────────────────────────────────
        doc.add_heading('二、课程目标', level=1)
        doc.add_paragraph(rd.get('module_2_objectives', '未填写'))

        # ── Module 3: Evaluation Standards ─────────────────────────────────
        doc.add_heading('三、课程评价标准', level=1)
        doc.add_paragraph(rd.get('module_3_evaluation_standards', '未填写'))

        # ── Module 4: Evaluation Results ───────────────────────────────────
        doc.add_heading('四、课程评价结果', level=1)
        eval_results = rd.get('module_4_evaluation_results', {})
        grade_analysis = eval_results.get('grade_analysis', {})
        if grade_analysis:
            for col_name, stats in grade_analysis.items():
                doc.add_heading(col_name, level=2)
                p = doc.add_paragraph()
                p.add_run(f'参考人数：{stats["count"]}　　')
                p.add_run(f'缺考人数：{stats["missing"]}　　')
                p.add_run(f'最高分：{stats["max"]}　　')
                p.add_run(f'最低分：{stats["min"]}　　')
                p.add_run(f'平均分：{stats["avg"]}　　')
                p.add_run(f'中位数：{stats["median"]}　　')
                p.add_run(f'标准差：{stats["stdev"]}　　')
                p.add_run(f'及格率：{stats["pass_rate"]}%')

                # Score distribution table
                doc.add_paragraph('成绩分布：')
                dist_table = doc.add_table(rows=1 + len(stats['distribution']), cols=3, style='Table Grid')
                dist_table.cell(0, 0).text = '分数段'
                dist_table.cell(0, 1).text = '人数'
                dist_table.cell(0, 2).text = '占比'
                dist_idx = 1
                total = stats['count']
                for key, dist in stats['distribution'].items():
                    dist_table.cell(dist_idx, 0).text = dist['label']
                    dist_table.cell(dist_idx, 1).text = str(dist['count'])
                    pct = round(dist['count'] / total * 100, 1) if total else 0
                    dist_table.cell(dist_idx, 2).text = f'{pct}%'
                    dist_idx += 1
        else:
            doc.add_paragraph('暂无成绩数据')

        # ── Module 5: Improvement Plan ─────────────────────────────────────
        doc.add_heading('五、课程持续改进方案及措施', level=1)
        doc.add_paragraph(rd.get('module_5_improvement_plan', '待后续版本实现'))

        from io import BytesIO

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)

        report.status = 'exported'
        report.save(update_fields=['status'])

        response = FileResponse(
            buf,
            as_attachment=True,
            filename=f'{report.report_name}.docx',
        )
        return response


class ReportListView(APIView):
    def get(self, request):
        course_id = request.query_params.get('course_id')
        class_id = request.query_params.get('class_id')
        semester_name = request.query_params.get('semester_name')

        qs = ReportRecord.objects.filter(user=request.user)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if class_id:
            qs = qs.filter(class_group_id=class_id)
        if semester_name:
            qs = qs.filter(semester__name=semester_name)

        serializer = ReportRecordSerializer(qs, many=True)
        return api_response(data=serializer.data)
