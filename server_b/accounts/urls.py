from django.urls import path, include # Added include
from .views import UserListView, UserCreateView, UserUpdateView, UserProfileView

app_name = 'accounts'
urlpatterns = [
    path('', include('django.contrib.auth.urls')), 
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/add/', UserCreateView.as_view(), name='user-add'),
    path('users/<int:pk>/', UserUpdateView.as_view(), name='user-edit'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
]
