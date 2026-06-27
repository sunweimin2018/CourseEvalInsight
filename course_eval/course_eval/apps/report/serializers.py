from rest_framework import serializers
from .models import ReportRecord


class ReportRecordSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    class_name = serializers.CharField(source='class_group.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    module_1_status_display = serializers.CharField(source='get_module_1_status_display', read_only=True)
    module_2_status_display = serializers.CharField(source='get_module_2_status_display', read_only=True)
    module_3_status_display = serializers.CharField(source='get_module_3_status_display', read_only=True)
    module_4_status_display = serializers.CharField(source='get_module_4_status_display', read_only=True)
    module_5_status_display = serializers.CharField(source='get_module_5_status_display', read_only=True)
    module_6_status_display = serializers.CharField(source='get_module_6_status_display', read_only=True)

    class Meta:
        model = ReportRecord
        fields = [
            'id', 'course', 'class_group', 'semester',
            'course_name', 'class_name', 'semester_name',
            'report_name', 'status', 'status_display',
            'report_file_path', 'created_time', 'updated_time',
            'module_1_status', 'module_2_status', 'module_3_status',
            'module_4_status', 'module_5_status', 'module_6_status',
            'module_1_status_display', 'module_2_status_display',
            'module_3_status_display', 'module_4_status_display',
            'module_5_status_display', 'module_6_status_display',
            'report_data',
        ]
        read_only_fields = ['id', 'created_time', 'updated_time']


class ReportGenerateSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    class_id = serializers.IntegerField()
    semester_name = serializers.CharField()


class ModuleUpdateSerializer(serializers.Serializer):
    """Validate per-module data update from user edits."""
    module_key = serializers.ChoiceField(choices=[
        ('module_1_course_info', '1'),
        ('module_2_objectives', '2'),
        ('module_3_evaluation_standards', '3'),
        ('module_4_evaluation_results', '4'),
        ('module_5_objective_achievement', '5'),
        ('module_6_improvement_plan', '6'),
    ])
    data = serializers.JSONField()
    confirmed = serializers.BooleanField(default=False)
