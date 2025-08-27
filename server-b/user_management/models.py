from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .rabbit import publish_user_event

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=255, blank=False, null=False)
    daily_quota = models.IntegerField(default=0) # New field

    def __str__(self):
        return self.user.username

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
    publish_user_event(instance, 'user.updated')

@receiver(post_delete, sender=User)
def delete_user_profile(sender, instance, **kwargs):
    publish_user_event(instance, 'user.deleted')
