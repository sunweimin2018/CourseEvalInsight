from rest_framework import serializers
from .models import ReportRecord


class ReportRecordSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    class_name = serializers.CharField(source='class_group.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ReportRecord
        fields = [
            'id', 'course', 'class_group', 'semester',
            'course_name', 'class_name', 'semester_name',
            'report_name', 'status', 'status_display',
            'report_file_path', 'created_time', 'updated_time',
        ]
        read_only_fields = ['id', 'created_time', 'updated_time']


class ReportGenerateSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    class_id = serializers.IntegerField()
    semester_name = serializers.CharField()
