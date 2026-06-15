from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, default='user')
    phone = models.CharField(max_length=20, blank=True, default='')
    avatar = models.CharField(max_length=255, blank=True, default='')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sys_user'
