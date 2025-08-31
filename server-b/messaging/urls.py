from django.urls import path
from .views import (
    UserMessageListView,
    AdminMessageListView,
    MessageDetailView,
    AdminMessageDetailView,
)

app_name = 'messaging'

urlpatterns = [
    path('my-messages/', UserMessageListView.as_view(), name='my_messages_list'),
    path('admin-messages/', AdminMessageListView.as_view(), name='admin_messages_list'),
    path(
        'admin-messages/<uuid:tracking_id>/',
        AdminMessageDetailView.as_view(),
        name='admin_message_detail',
    ),
    path('messages/<uuid:tracking_id>/', MessageDetailView.as_view(), name='message_detail'),
]
