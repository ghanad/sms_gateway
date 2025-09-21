from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path(
        '',
        RedirectView.as_view(
            pattern_name='messaging:my_messages_list', permanent=True
        ),
    ),
    path('settings/', views.settings, name='settings'),
]
