from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.ExcelUploadView.as_view(), name='excel-upload'),
    path('raw-data/', views.RawDataView.as_view(), name='excel-raw-data'),
    path('clean/', views.CleanDataView.as_view(), name='excel-clean'),
    path('cleaned-data/', views.CleanedDataPreviewView.as_view(), name='excel-cleaned-data'),
    # Course / Class / Semester
    path('courses/', views.CourseListView.as_view(), name='course-list'),
    path('classes/', views.ClassGroupListView.as_view(), name='class-list'),
    path('semesters/', views.SemesterListView.as_view(), name='semester-list'),
    # Course files
    path('course-files/upload/', views.CourseFileUploadView.as_view(), name='course-file-upload'),
    path('course-files/', views.CourseFileListView.as_view(), name='course-file-list'),
    path('course-files/<int:pk>/', views.CourseFileDeleteView.as_view(), name='course-file-delete'),
]
