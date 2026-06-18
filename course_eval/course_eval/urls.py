from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/user/', include('course_eval.apps.user.urls')),
    path('api/v1/excel/', include('course_eval.apps.excel.urls')),
    path('api/v1/report/', include('course_eval.apps.report.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
