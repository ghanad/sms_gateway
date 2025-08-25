from django.forms import widgets


class TextInput(widgets.TextInput):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'input'}  # مطابق dashboard.css
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class Textarea(widgets.Textarea):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'field'}  # textarea ساده با استایل مشترک
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class Select(widgets.Select):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'field'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class CheckboxInput(widgets.CheckboxInput):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'checkbox'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

