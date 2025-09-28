from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def replace_query(context, **kwargs):
    """Return encoded query string with updated parameters."""
    request = context.get('request')
    if request is None:
        query_params = {}
    else:
        query_params = request.GET.copy()

    for key, value in kwargs.items():
        if value in (None, ''):
            query_params.pop(key, None)
        else:
            query_params[key] = value

    encoded = query_params.urlencode() if hasattr(query_params, 'urlencode') else urlencode(query_params)
    return f'?{encoded}' if encoded else ''
