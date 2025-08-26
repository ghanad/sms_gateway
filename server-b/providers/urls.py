from django.urls import path
from .views import (
    SmsProviderListView,
    SmsProviderCreateView,
    SmsProviderUpdateView,
    SmsProviderDeleteView,
    ToggleProviderStatusView,
    SendTestSmsView,
)

urlpatterns = [
    path('', SmsProviderListView.as_view(), name='sms_provider_list'),
    path('add/', SmsProviderCreateView.as_view(), name='sms_provider_add'),
    path('<int:pk>/edit/', SmsProviderUpdateView.as_view(), name='sms_provider_edit'),
    path('<int:pk>/delete/', SmsProviderDeleteView.as_view(), name='sms_provider_delete'),
    path('<int:pk>/toggle-status/', ToggleProviderStatusView.as_view(), name='toggle_provider_status'),
    path('<int:pk>/test/', SendTestSmsView.as_view(), name='sms_provider_test'),
]
