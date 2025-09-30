from django.urls import path
from .views import (
    ConfigExportView,
    ToggleUserStatusView,
    UserCreateView,
    UserDeleteView,
    UserListView,
    UserStatsView,
    UserPasswordChangeView,
    UserUpdateView,
    my_profile,
)

urlpatterns = [
    path('profile/', my_profile, name='my_profile'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('user-stats/', UserStatsView.as_view(), name='user_stats'),
    path('users/export-config/', ConfigExportView.as_view(), name='config_export'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/toggle_status/', ToggleUserStatusView.as_view(), name='user_toggle'),
    path('users/<int:pk>/password/', UserPasswordChangeView.as_view(), name='user_password_change'),
]