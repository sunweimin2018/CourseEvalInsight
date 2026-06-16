from rest_framework import serializers
from .models import Course, ClassGroup, Semester, CourseFileRecord


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'name', 'create_time']
        read_only_fields = ['id', 'create_time']


class ClassGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassGroup
        fields = ['id', 'name', 'create_time']
        read_only_fields = ['id', 'create_time']


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ['id', 'name', 'create_time']
        read_only_fields = ['id', 'create_time']


class CourseFileRecordSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    class_name = serializers.CharField(source='class_group.name', read_only=True)
    semester_name = serializers.CharField(source='semester.name', read_only=True)
    file_type_display = serializers.CharField(source='get_file_type_display', read_only=True)

    class Meta:
        model = CourseFileRecord
        fields = [
            'id', 'course', 'class_group', 'semester',
            'course_name', 'class_name', 'semester_name',
            'file_type', 'file_type_display', 'file_name',
            'file_size', 'upload_time',
        ]
        read_only_fields = ['id', 'upload_time']


class CourseFileUploadSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    class_id = serializers.IntegerField()
    semester_id = serializers.IntegerField()
    file_type = serializers.ChoiceField(choices=CourseFileRecord.FILE_TYPES)
    file = serializers.FileField()


class ExcelUploadSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        max_length=10,
    )
