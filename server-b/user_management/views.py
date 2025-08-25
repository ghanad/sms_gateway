from django.contrib.auth.models import User
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'user_management/user_list.html'
    context_object_name = 'users'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = UserCreationForm()
        context['update_form'] = UserChangeForm() # This will be an empty form initially
        return context

class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'user_management/user_create.html' # Render user_create.html
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error creating user. Please check the form.")
        # This is tricky for modals. We need to re-render the list page with the form errors.
        # A common pattern is to redirect back with messages, or use AJAX.
        # For now, we'll redirect and rely on messages.
        return redirect(reverse_lazy('user_list')) # Redirect back to list on error

class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = UserChangeForm
    template_name = 'user_management/user_list.html' # Render user_list.html
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error updating user. Please check the form.")
        return redirect(reverse_lazy('user_list')) # Redirect back to list on error

class UserDeleteView(StaffRequiredMixin, DeleteView):
    model = User
    template_name = 'user_management/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User deleted successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error deleting user.")
        return redirect(reverse_lazy('user_list'))


class UserToggleActiveView(StaffRequiredMixin, View):
    """Toggle a user's active status."""

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = not user.is_active
        user.save()
        if user.is_active:
            messages.success(request, "User enabled successfully!")
        else:
            messages.success(request, "User disabled successfully!")
        return redirect(reverse_lazy('user_list'))
