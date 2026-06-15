from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='user-login'),
    path('logout/', views.LogoutView.as_view(), name='user-logout'),
    path('register/', views.RegisterView.as_view(), name='user-register'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    path('check-username/', views.CheckUsernameView.as_view(), name='check-username'),
    path('profile/', views.ProfileView.as_view(), name='user-profile'),
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
]
