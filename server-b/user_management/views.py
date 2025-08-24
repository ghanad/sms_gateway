from django.contrib.auth.models import User
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'user_management/user_list.html'
    context_object_name = 'users'

class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'user_management/user_form.html'
    success_url = reverse_lazy('user_list')

class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = UserChangeForm
    template_name = 'user_management/user_form.html'
    success_url = reverse_lazy('user_list')

class UserDeleteView(StaffRequiredMixin, DeleteView):
    model = User
    template_name = 'user_management/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')