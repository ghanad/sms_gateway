from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView
from .models import Message


class UserMessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/message_list.html'
    context_object_name = 'messages'
    paginate_by = 25

    def get_queryset(self):
        return Message.objects.filter(user=self.request.user).order_by('-sent_at')

class AdminMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Message
    template_name = 'messaging/admin_message_list.html'
    context_object_name = 'messages'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Message.objects.all().order_by('-sent_at')
