from django.db import models
from django.contrib.auth.models import User


class ExcelFile(models.Model):
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    upload_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='excel_files')

    class Meta:
        db_table = 'excel_file'
        ordering = ['-upload_time']


class Course(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course'
        unique_together = [('name', 'user')]
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='class_groups')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_group'
        unique_together = [('name', 'user')]
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class Semester(models.Model):
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='semesters')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'semester'
        unique_together = [('name', 'user')]
        ordering = ['-create_time']

    def __str__(self):
        return self.name


class CourseFileRecord(models.Model):
    FILE_TYPES = [
        ('syllabus', '课程大纲'),
        ('student_info', '学生基本信息表'),
        ('grades', '学生成绩表'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='file_records')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='file_records')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='file_records')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_file_records')
    upload_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_file_record'
        unique_together = [('course', 'class_group', 'semester', 'file_type', 'user')]
        ordering = ['file_type']


class WorkbookSnapshot(models.Model):
    """Persistent save of a user-modified working copy for report generation."""
    source_file = models.ForeignKey(
        CourseFileRecord, on_delete=models.CASCADE, related_name='snapshots'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workbook_snapshots')
    headers = models.JSONField()
    rows = models.JSONField()
    row_count = models.IntegerField()
    created_time = models.DateTimeField(auto_now_add=True)
    is_latest = models.BooleanField(default=True)

    class Meta:
        db_table = 'workbook_snapshot'
        ordering = ['-created_time']
        indexes = [
            models.Index(fields=['source_file', 'is_latest']),
        ]
