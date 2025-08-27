from django.urls import path
from .views import UserMessageListView

app_name = 'messaging'

urlpatterns = [
    path('my-messages/', UserMessageListView.as_view(), name='my_messages_list'),
]
