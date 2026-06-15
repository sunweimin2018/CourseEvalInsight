from rest_framework import serializers

ALLOWED_EXTENSIONS = {'.xlsx', '.xls'}
MAX_FILE_SIZE_MB = 10
MAX_FILE_COUNT = 10


def validate_file_extension(name):
    import os
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(f'Invalid file type "{name}". Only .xlsx and .xls are allowed.')
    return name


def validate_file_size(size):
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise serializers.ValidationError(
            f'File size ({size / 1024 / 1024:.1f}MB) exceeds the {MAX_FILE_SIZE_MB}MB limit.'
        )


def validate_file_count(files):
    if len(files) > MAX_FILE_COUNT:
        raise serializers.ValidationError(
            f'Too many files ({len(files)}). Maximum {MAX_FILE_COUNT} files per upload.'
        )
