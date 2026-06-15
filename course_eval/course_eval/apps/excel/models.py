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
