from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.ReportGenerateView.as_view(), name='report-generate'),
    path('preview/<int:pk>/', views.ReportPreviewView.as_view(), name='report-preview'),
    path('export/<int:pk>/', views.ReportExportView.as_view(), name='report-export'),
    path('', views.ReportListView.as_view(), name='report-list'),

    # Per-module endpoints
    path('<int:pk>/module/<int:module_num>/generate/', views.ModuleGenerateView.as_view(), name='module-generate'),
    path('<int:pk>/module/<int:module_num>/update/', views.ModuleUpdateView.as_view(), name='module-update'),
    path('<int:pk>/module/<int:module_num>/export-docx/', views.ModuleExportView.as_view(), name='module-export'),

    # Merge endpoint
    path('<int:pk>/merge/', views.ReportMergeView.as_view(), name='report-merge'),
]
