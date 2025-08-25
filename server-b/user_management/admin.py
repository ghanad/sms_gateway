from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'
    fk_name = 'user'
    fields = ('api_key',) # Only show api_key in the inline form

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = UserAdmin.list_display + ('get_api_key',) # Add get_api_key to list display

    def get_api_key(self, instance):
        return instance.profile.api_key
    get_api_key.short_description = 'API Key' # Column header

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)