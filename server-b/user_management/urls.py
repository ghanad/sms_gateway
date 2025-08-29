from django.urls import path
from .views import (
    UserListView,
    UserCreateView,
    UserUpdateView,
    UserDeleteView,
    ToggleUserStatusView,
    UserPasswordChangeView,
)

urlpatterns = [
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/update/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/toggle_status/', ToggleUserStatusView.as_view(), name='user_toggle'),
    path('users/<int:pk>/password/', UserPasswordChangeView.as_view(), name='user_password_change'),
]