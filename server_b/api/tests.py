from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from messaging.models import Message
from providers.models import Provider

class MessageApiTest(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name='Magfa', type='magfa', base_url='http://example.com',
            endpoint_send='/send', auth_type='none'
        )
        self.msg = Message.objects.create(tracking_id='track1', customer_id='c1', provider=self.provider,
                                          payload_hash='h', idempotency_key='i')
    def test_requires_jwt(self):
        client = APIClient()
        url = reverse('message-tracking', args=[self.msg.tracking_id])
        resp = client.get(url)
        assert resp.status_code == 401
