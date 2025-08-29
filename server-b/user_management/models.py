from django.db import models
from django.contrib.auth.models import User
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=255, blank=False, null=False)
    daily_quota = models.IntegerField(default=0) # New field

    def __str__(self):
        return self.user.username

