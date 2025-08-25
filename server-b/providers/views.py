from django.shortcuts import render
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from .models import SmsProvider
from .forms import SmsProviderForm

class SmsProviderListView(ListView):
    model = SmsProvider
    template_name = 'providers/sms_provider_list.html'
    context_object_name = 'sms_providers'

class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class SmsProviderCreateView(IsAdminMixin, CreateView):
    model = SmsProvider
    form_class = SmsProviderForm
    template_name = 'providers/smsprovider_form.html'
    success_url = reverse_lazy('sms_provider_list')

class SmsProviderUpdateView(IsAdminMixin, UpdateView):
    model = SmsProvider
    form_class = SmsProviderForm
    template_name = 'providers/smsprovider_form.html'
    success_url = reverse_lazy('sms_provider_list')

class SmsProviderDeleteView(IsAdminMixin, DeleteView):
    model = SmsProvider
    template_name = 'providers/smsprovider_confirm_delete.html'
    success_url = reverse_lazy('sms_provider_list')
