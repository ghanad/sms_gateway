from rest_framework import serializers
from messaging.models import Message, MessageEvent
from providers.models import Provider

class MessageEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageEvent
        fields = ['event_type', 'raw', 'at']

class MessageSerializer(serializers.ModelSerializer):
    events = MessageEventSerializer(many=True, read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)

    class Meta:
        model = Message
        fields = ['tracking_id', 'status', 'provider_name', 'provider_message_id', 'updated_at', 'events']

class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ['id', 'name', 'type']
