from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView
from .models import Message
import uuid


class UserMessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/message_list.html'
    context_object_name = 'message_list'
    paginate_by = 25

    def get_queryset(self):
        queryset = Message.objects.filter(user=self.request.user).order_by('-sent_at')
        tracking_id = self.request.GET.get('tracking_id', '').strip()
        if tracking_id:
            try:
                uuid_obj = uuid.UUID(tracking_id)
                queryset = queryset.filter(tracking_id=uuid_obj)
            except ValueError:
                queryset = Message.objects.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tracking_id'] = self.request.GET.get('tracking_id', '').strip()
        return context

class AdminMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Message
    template_name = 'messaging/admin_message_list.html'
    context_object_name = 'message_list'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Message.objects.all().order_by('-sent_at')


class MessageDetailView(LoginRequiredMixin, DetailView):
    model = Message
    template_name = 'messaging/message_detail.html'
    slug_field = 'tracking_id'
    slug_url_kwarg = 'tracking_id'

    def get_queryset(self):
        return Message.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attempt_logs'] = self.object.attempt_logs.select_related('provider').all()
        return context


class AdminMessageDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Message
    template_name = 'messaging/message_detail.html'
    slug_field = 'tracking_id'
    slug_url_kwarg = 'tracking_id'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Message.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attempt_logs'] = self.object.attempt_logs.select_related('provider').all()
        return context
