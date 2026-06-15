from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.ExcelUploadView.as_view(), name='excel-upload'),
    path('raw-data/', views.RawDataView.as_view(), name='excel-raw-data'),
    path('clean/', views.CleanDataView.as_view(), name='excel-clean'),
    path('cleaned-data/', views.CleanedDataPreviewView.as_view(), name='excel-cleaned-data'),
]
