from django.urls import path
from .views import UserListView, UserCreateView, UserUpdateView

app_name = 'accounts'
urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/add/', UserCreateView.as_view(), name='user-add'),
    path('users/<int:pk>/', UserUpdateView.as_view(), name='user-edit'),
]
