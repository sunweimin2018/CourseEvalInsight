from django.db import models
from django.contrib.auth.models import User
from course_eval.apps.excel.models import Course, ClassGroup, Semester, CourseFileRecord


class ReportRecord(models.Model):
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('completed', '已生成'),
        ('exported', '已导出'),
    ]

    MODULE_STATUS = [
        ('pending', '待生成'),
        ('draft', '草稿'),
        ('confirmed', '已确认'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reports')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='reports')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')

    syllabus_file = models.ForeignKey(
        CourseFileRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='report_syllabus'
    )
    student_info_file = models.ForeignKey(
        CourseFileRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='report_student_info'
    )
    grades_file = models.ForeignKey(
        CourseFileRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='report_grades'
    )

    report_name = models.CharField(max_length=255)
    report_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    report_file_path = models.CharField(max_length=500, blank=True, default='')

    module_1_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)
    module_2_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)
    module_3_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)
    module_4_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)
    module_5_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)
    module_6_status = models.CharField(max_length=20, default='pending', choices=MODULE_STATUS)

    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_record'
        ordering = ['-created_time']
        unique_together = [('course', 'class_group', 'semester', 'user')]
