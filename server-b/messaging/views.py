from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Message


class UserMessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/message_list.html'
    context_object_name = 'messages'
    paginate_by = 25

    def get_queryset(self):
        return Message.objects.filter(user=self.request.user).order_by('-sent_at')
