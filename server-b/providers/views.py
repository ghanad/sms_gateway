from django.shortcuts import render
from django.views.generic import ListView, View
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from .models import SmsProvider
from .forms import SmsProviderForm, SendTestSmsForm
from django.http import JsonResponse

class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

class SmsProviderListView(ListView):
    model = SmsProvider
    template_name = 'providers/sms_provider_list.html'
    context_object_name = 'sms_providers'

class CheckBalanceView(IsAdminMixin, View):
    def get(self, request, pk):
        provider = SmsProvider.objects.get(pk=pk)
        adapter = get_provider_adapter(provider)
        balance = adapter.get_balance()
        return JsonResponse(balance)
    def test_func(self):
        return self.request.user.is_staff

from .models import ProviderType

class SmsProviderCreateView(IsAdminMixin, CreateView):
    model = SmsProvider
    form_class = SmsProviderForm
    template_name = 'providers/smsprovider_form.html'
    success_url = reverse_lazy('sms_provider_list')

    def form_valid(self, form):
        form.instance.provider_type = ProviderType.MAGFA
        if form.instance.query_params is None:
            form.instance.query_params = {}
        return super().form_valid(form)

class SmsProviderUpdateView(IsAdminMixin, UpdateView):
    model = SmsProvider
    form_class = SmsProviderForm
    template_name = 'providers/smsprovider_form.html'
    success_url = reverse_lazy('sms_provider_list')

class SmsProviderDeleteView(IsAdminMixin, DeleteView):
    model = SmsProvider
    template_name = 'providers/smsprovider_confirm_delete.html'
    success_url = reverse_lazy('sms_provider_list')

class ToggleProviderStatusView(IsAdminMixin, View):
    def post(self, request, pk):
        try:
            provider = SmsProvider.objects.get(pk=pk)
            data = json.loads(request.body)
            provider.is_active = data.get('is_active', provider.is_active)
            provider.save()
            return JsonResponse({'success': True, 'is_active': provider.is_active})
        except SmsProvider.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Provider not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

from .adapters import get_provider_adapter

class SendTestSmsView(IsAdminMixin, FormView):
    form_class = SendTestSmsForm
    template_name = 'providers/send_test_sms.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider = SmsProvider.objects.get(pk=self.kwargs['pk'])
        context['provider'] = provider
        return context

    def form_valid(self, form):
        provider = SmsProvider.objects.get(pk=self.kwargs['pk'])
        recipient = form.cleaned_data['recipient']
        message = form.cleaned_data['message']

        adapter = get_provider_adapter(provider)
        result = adapter.send_sms(recipient, message)

        context = self.get_context_data()
        context['result'] = result
        return self.render_to_response(context)
