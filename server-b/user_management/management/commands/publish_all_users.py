from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from user_management.rabbit import publish_user_event

class Command(BaseCommand):
    help = 'Publishes all users to the config_events_exchange'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            self.stdout.write(f'Publishing user {user.username}')
            publish_user_event(user, 'user.updated')
        self.stdout.write(self.style.SUCCESS('Successfully published all users'))
