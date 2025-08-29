from django.contrib.auth.models import User
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .forms import CustomUserChangeForm, CustomUserCreationForm
from django.contrib.auth.views import PasswordChangeView


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
        context['update_form'] = UserChangeForm()  # This will be an empty form initially
        return context


class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm # Use the custom creation form
    template_name = 'user_management/user_form.html'  # Render user_form.html
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error creating user. Please check the form.")
        return redirect(reverse_lazy('user_list'))


class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm  # Use the custom form
    template_name = 'user_management/user_form.html'  # Render user_form.html
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error updating user. Please check the form.")
        return redirect(reverse_lazy('user_list'))


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


@method_decorator(csrf_exempt, name='dispatch')
class ToggleUserStatusView(StaffRequiredMixin, View):
    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = not user.is_active
            user.save()
            return JsonResponse({'success': True, 'is_active': user.is_active})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = not user.is_active
        user.save()
        return redirect('user_list')


from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordChangeForm, SetPasswordForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .forms import CustomUserChangeForm, CustomUserCreationForm
from django.contrib.auth.views import PasswordChangeView


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


# ... (other views) ...


class UserPasswordChangeView(StaffRequiredMixin, PasswordChangeView):
    form_class = SetPasswordForm # Use SetPasswordForm
    template_name = 'user_management/password_change_form.html' # We will create this template
    success_url = reverse_lazy('user_list') # Redirect to user list after successful change

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Get the user whose password is to be changed
        user_to_change = get_object_or_404(User, pk=self.kwargs['pk'])
        kwargs['user'] = user_to_change
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "User password changed successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Error changing user password. Please check the form.")
        return super().form_invalid(form)