from django.urls import path
from .views import (
    SmsProviderListView,
    SmsProviderCreateView,
    SmsProviderUpdateView,
    SmsProviderDeleteView,
)

urlpatterns = [
    path('', SmsProviderListView.as_view(), name='sms_provider_list'),
    path('add/', SmsProviderCreateView.as_view(), name='sms_provider_add'),
    path('<int:pk>/edit/', SmsProviderUpdateView.as_view(), name='sms_provider_edit'),
    path('<int:pk>/delete/', SmsProviderDeleteView.as_view(), name='sms_provider_delete'),
]
