from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, TemplateView

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'

class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    fields = ['username', 'email', 'is_staff', 'is_active']
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user-list')

class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    fields = ['username', 'email', 'is_staff', 'is_active']
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user-list')

class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/user_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context
