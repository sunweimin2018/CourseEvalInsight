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
    # Data Preview – Word
    path('course-files/<int:pk>/word-content/', views.WordContentView.as_view(), name='course-file-word-content'),
    # Data Preview – Excel CRUD
    path('course-files/<int:pk>/data/open/', views.OpenWorkingCopyView.as_view(), name='course-file-open'),
    path('course-files/<int:pk>/data/', views.WorkingDataView.as_view(), name='course-file-data'),
    path('course-files/<int:pk>/data/add-row/', views.AddRowView.as_view(), name='course-file-add-row'),
    path('course-files/<int:pk>/data/update-cell/', views.UpdateCellView.as_view(), name='course-file-update-cell'),
    path('course-files/<int:pk>/data/delete-row/', views.DeleteRowView.as_view(), name='course-file-delete-row'),
    path('course-files/<int:pk>/data/save/', views.SaveSnapshotView.as_view(), name='course-file-save'),
    path('course-files/<int:pk>/data/reset/', views.ResetWorkingCopyView.as_view(), name='course-file-reset'),
]
