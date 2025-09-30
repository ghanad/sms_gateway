from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import dateformat
from django.views.generic import ListView, DetailView
from .models import Message
from .forms import MessageFilterForm
import uuid


class UserMessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/message_list.html'
    context_object_name = 'message_list'
    paginate_by = 10

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
        paginator = context.get('paginator')
        page_obj = context.get('page_obj')
        if paginator and page_obj:
            context['page_range'] = paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        else:
            context['page_range'] = []
        return context

class AdminMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Message
    template_name = 'messaging/admin_message_list.html'
    context_object_name = 'message_list'
    paginate_by = 10

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        self.filter_form = MessageFilterForm(self.request.GET or None)
        queryset = Message.objects.all().order_by('-sent_at')

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data

            user = data.get('user')
            if user:
                queryset = queryset.filter(user=user)

            status = data.get('status')
            if status:
                queryset = queryset.filter(status=status)

            provider = data.get('provider')
            if provider:
                queryset = queryset.filter(provider=provider)

            date_from = self.filter_form.get_date_from_datetime()
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)

            date_to = self.filter_form.get_date_to_datetime()
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = getattr(self, 'filter_form', MessageFilterForm(self.request.GET or None))
        active_filters = filter_form.get_active_filters()

        context['filter_form'] = filter_form
        context['active_filters'] = active_filters
        context['active_filter_count'] = len(active_filters)
        context['filter_panel_open'] = bool(active_filters or filter_form.errors)

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')

        active_filter_chips = []

        def build_remove_url(*field_names):
            reduced = query_params.copy()
            for name in field_names:
                if name in reduced:
                    reduced.pop(name)
            encoded = reduced.urlencode()
            return f"{self.request.path}?{encoded}" if encoded else self.request.path

        user_filter_display = None
        user_value = active_filters.get('user') if active_filters else None
        if user_value:
            user_filter_display = filter_form.fields['user'].label_from_instance(user_value)
            active_filter_chips.append(
                {
                    'field': 'user',
                    'label': filter_form.fields['user'].label,
                    'value': user_filter_display,
                    'remove_url': build_remove_url('user'),
                }
            )
        context['active_filter_user_display'] = user_filter_display

        status_value = active_filters.get('status') if active_filters else None
        if status_value:
            status_label = dict(filter_form.fields['status'].choices).get(status_value, status_value)
            active_filter_chips.append(
                {
                    'field': 'status',
                    'label': filter_form.fields['status'].label,
                    'value': status_label,
                    'remove_url': build_remove_url('status'),
                }
            )

        provider_value = active_filters.get('provider') if active_filters else None
        if provider_value:
            active_filter_chips.append(
                {
                    'field': 'provider',
                    'label': filter_form.fields['provider'].label,
                    'value': provider_value.name,
                    'remove_url': build_remove_url('provider'),
                }
            )

        date_from_value = active_filters.get('date_from') if active_filters else None
        if date_from_value:
            active_filter_chips.append(
                {
                    'field': 'date_from',
                    'label': filter_form.fields['date_from'].label,
                    'value': dateformat.format(date_from_value, 'M j, Y'),
                    'remove_url': build_remove_url('date_from'),
                }
            )

        date_to_value = active_filters.get('date_to') if active_filters else None
        if date_to_value:
            active_filter_chips.append(
                {
                    'field': 'date_to',
                    'label': filter_form.fields['date_to'].label,
                    'value': dateformat.format(date_to_value, 'M j, Y'),
                    'remove_url': build_remove_url('date_to'),
                }
            )

        context['active_filter_chips'] = active_filter_chips

        paginator = context.get('paginator')
        page_obj = context.get('page_obj')
        if paginator and page_obj:
            context['page_range'] = paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        else:
            context['page_range'] = []
        return context


class MessageDetailView(LoginRequiredMixin, DetailView):
    model = Message
    template_name = 'messaging/message_detail.html'
    slug_field = 'tracking_id'
    slug_url_kwarg = 'tracking_id'

    def get_queryset(self):
        return (
            Message.objects.select_related('provider', 'user')
            .filter(user=self.request.user)
        )

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
        return Message.objects.select_related('provider', 'user').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attempt_logs'] = self.object.attempt_logs.select_related('provider').all()
        return context
