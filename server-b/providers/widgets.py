from django.forms import widgets

class TextInput(widgets.TextInput):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

class Textarea(widgets.Textarea):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

class Select(widgets.Select):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

class CheckboxInput(widgets.CheckboxInput):
    def __init__(self, attrs=None):
        default_attrs = {'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
