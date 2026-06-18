from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.ReportGenerateView.as_view(), name='report-generate'),
    path('preview/<int:pk>/', views.ReportPreviewView.as_view(), name='report-preview'),
    path('export/<int:pk>/', views.ReportExportView.as_view(), name='report-export'),
    path('', views.ReportListView.as_view(), name='report-list'),
]
