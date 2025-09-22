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
    path('docs/server-a/', views.server_a_user_guide, name='server_a_user_guide'),
]
