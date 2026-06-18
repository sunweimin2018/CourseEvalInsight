from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from course_eval.utils.response import api_response
from .models import ReportRecord
from .serializers import ReportRecordSerializer, ReportGenerateSerializer
from .report_engine import generate_report
from .pdf_engine import generate_pdf


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
        report = ReportRecord.objects.filter(id=pk, user=request.user).first()
        if not report:
            return api_response(code=404, msg='报告不存在', http_status=404)

        export_format = request.query_params.get('export_format', 'docx')

        if export_format == 'pdf':
            return self._export_pdf(report)
        return self._export_docx(report)

    def _export_docx(self, report):
        from django.http import FileResponse
        from docx import Document
        from docx.shared import Inches, Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        rd = report.report_data
        doc = Document()

        # ── Set default font to 宋体 ──────────────────────────────────────
        default_style = doc.styles['Normal']
        default_style.font.name = '宋体'
        default_style.font.size = Pt(12)

        def _run_font(run, font_name='宋体', font_size=Pt(12)):
            run.font.name = font_name
            run.font.size = font_size
            return run

        def _set_cell(cell, text, bold=False):
            cell.text = ''
            run = cell.paragraphs[0].add_run(str(text))
            _run_font(run)
            if bold:
                run.bold = True

        # Title
        title = doc.add_heading(report.report_name, level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in title.runs:
            _run_font(run)

        # ── Module 1: Course Basic Info Table ──────────────────────────────
        h = doc.add_heading('一、课程基本信息表', level=1)
        for run in h.runs:
            _run_font(run)
        info = rd.get('module_1_course_info', {})
        table = doc.add_table(rows=7, cols=4, style='Table Grid')

        # Row 0-4: standard two-pair rows
        rows_data = [
            ['课程名称：', info.get('course_name', ''), '修课人数：', str(info.get('student_count', ''))],
            ['课程编号：', info.get('course_code', ''), '课序号：', str(info.get('course_seq', ''))],
            ['授课班级：', info.get('teaching_class', ''), '学时数：', str(info.get('total_hours', ''))],
            ['选用教材：', info.get('textbook', ''), '学分：', str(info.get('credits', ''))],
            ['开课院系：', info.get('department', ''), '授课教师：', str(info.get('teacher', ''))],
        ]
        for r_idx, (lbl1, val1, lbl2, val2) in enumerate(rows_data):
            _set_cell(table.cell(r_idx, 0), lbl1, bold=True)
            _set_cell(table.cell(r_idx, 1), val1)
            _set_cell(table.cell(r_idx, 2), lbl2, bold=True)
            _set_cell(table.cell(r_idx, 3), val2)

        # Row 5: 课程性质 — cols 1-3 merged for the value
        _set_cell(table.cell(5, 0), '课程性质：', bold=True)
        table.cell(5, 1).merge(table.cell(5, 3))
        _set_cell(table.cell(5, 1), info.get('course_nature', ''))

        # Row 6: 课程类型 — cols 1-3 merged for the value
        _set_cell(table.cell(6, 0), '课程类型：', bold=True)
        table.cell(6, 1).merge(table.cell(6, 3))
        _set_cell(table.cell(6, 1), info.get('course_type', ''))

        # ── Module 2: Course Objectives ────────────────────────────────────
        h = doc.add_heading('二、课程目标', level=1)
        for run in h.runs:
            _run_font(run)
        p = doc.add_paragraph(rd.get('module_2_objectives', '未填写'))
        for run in p.runs:
            _run_font(run)

        # ── Module 3: Evaluation Standards ─────────────────────────────────
        h = doc.add_heading('三、课程评价标准', level=1)
        for run in h.runs:
            _run_font(run)
        eval_data = rd.get('module_3_evaluation_standards', '未填写')
        if isinstance(eval_data, list):
            for block in eval_data:
                if block['type'] == 'paragraph':
                    p = doc.add_paragraph(block['text'])
                    for run in p.runs:
                        _run_font(run)
                elif block['type'] == 'table':
                    grid = block['grid']
                    num_cols = block['num_cols']
                    if not grid or num_cols == 0:
                        continue
                    num_rows = len(grid)
                    tbl = doc.add_table(rows=num_rows, cols=num_cols, style='Table Grid')
                    for r in range(num_rows):
                        for c in range(num_cols):
                            cell_data = grid[r][c]
                            if cell_data is None:
                                continue
                            cell = tbl.cell(r, c)
                            _set_cell(cell, cell_data['text'], bold=(r == 0))
                            if cell_data['colspan'] > 1 or cell_data['rowspan'] > 1:
                                end_r = r + cell_data['rowspan'] - 1
                                end_c = c + cell_data['colspan'] - 1
                                cell.merge(tbl.cell(end_r, end_c))
        else:
            p = doc.add_paragraph(eval_data)
            for run in p.runs:
                _run_font(run)

        # ── Module 4: Evaluation Results ───────────────────────────────────
        h = doc.add_heading('四、课程评价结果', level=1)
        for run in h.runs:
            _run_font(run)
        eval_results = rd.get('module_4_evaluation_results', {})
        grade_analysis = eval_results.get('grade_analysis', {})
        if grade_analysis:
            for col_name, stats in grade_analysis.items():
                h2 = doc.add_heading(col_name, level=2)
                for run in h2.runs:
                    _run_font(run)
                p = doc.add_paragraph()
                for label, val in [
                    ('参考人数：', stats['count']),
                    ('缺考人数：', stats['missing']),
                    ('最高分：', stats['max']),
                    ('最低分：', stats['min']),
                    ('平均分：', stats['avg']),
                    ('中位数：', stats['median']),
                    ('标准差：', stats['stdev']),
                ]:
                    _run_font(p.add_run(f'{label}{val}　　'))
                _run_font(p.add_run(f'及格率：{stats["pass_rate"]}%'))

                # Score distribution table
                dp = doc.add_paragraph('成绩分布：')
                for run in dp.runs:
                    _run_font(run)
                dist_table = doc.add_table(rows=1 + len(stats['distribution']), cols=3, style='Table Grid')
                _set_cell(dist_table.cell(0, 0), '分数段', bold=True)
                _set_cell(dist_table.cell(0, 1), '人数', bold=True)
                _set_cell(dist_table.cell(0, 2), '占比', bold=True)
                dist_idx = 1
                total = stats['count']
                for key, dist in stats['distribution'].items():
                    _set_cell(dist_table.cell(dist_idx, 0), dist['label'])
                    _set_cell(dist_table.cell(dist_idx, 1), str(dist['count']))
                    pct = round(dist['count'] / total * 100, 1) if total else 0
                    _set_cell(dist_table.cell(dist_idx, 2), f'{pct}%')
                    dist_idx += 1
        else:
            p = doc.add_paragraph('暂无成绩数据')
            for run in p.runs:
                _run_font(run)

        # ── Module 5: Improvement Plan ─────────────────────────────────────
        h = doc.add_heading('五、课程持续改进方案及措施', level=1)
        for run in h.runs:
            _run_font(run)
        p = doc.add_paragraph(rd.get('module_5_improvement_plan', '待后续版本实现'))
        for run in p.runs:
            _run_font(run)

        from io import BytesIO

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)

        report.status = 'exported'
        report.save(update_fields=['status'])

        return FileResponse(
            buf,
            as_attachment=True,
            filename=f'{report.report_name}.docx',
        )

    def _export_pdf(self, report):
        from django.http import FileResponse

        buf = generate_pdf(report.report_name, report.report_data)

        report.status = 'exported'
        report.save(update_fields=['status'])

        return FileResponse(
            buf,
            as_attachment=True,
            filename=f'{report.report_name}.pdf',
            content_type='application/pdf',
        )


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
