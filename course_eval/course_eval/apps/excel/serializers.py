from rest_framework import serializers


class ExcelUploadSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        max_length=10,
    )
