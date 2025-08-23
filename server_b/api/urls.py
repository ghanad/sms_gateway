from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MessageTrackingView, ProviderViewSet

router = DefaultRouter()
router.register(r'providers', ProviderViewSet, basename='provider')

urlpatterns = [
    path('messages/<str:tracking_id>/', MessageTrackingView.as_view(), name='message-tracking'),
    path('', include(router.urls)),
]
