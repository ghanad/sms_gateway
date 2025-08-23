import os
import jwt
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.decorators import action
from messaging.models import Message
from providers.models import Provider
from providers import registry
from .serializers import MessageSerializer, ProviderSerializer

class MessageTrackingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tracking_id):
        token = request.headers.get('Authorization', '').split('Bearer ')
        if len(token) != 2:
            return Response({'detail': 'Unauthorized'}, status=401)
        token = token[1]
        try:
            data = jwt.decode(token, os.getenv('JWT_SHARED_SECRET', ''), algorithms=['HS256'])
        except Exception:
            return Response({'detail': 'Unauthorized'}, status=401)
        if data.get('tid') != tracking_id or 'cid' not in data:
            return Response({'detail': 'Forbidden'}, status=403)
        msg = get_object_or_404(Message, tracking_id=tracking_id)
        return Response(MessageSerializer(msg).data)

class ProviderViewSet(ReadOnlyModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        provider = self.get_object()
        ProviderCls = registry.get(provider.type)
        prov = ProviderCls()
        result = prov.get_balance(provider.__dict__)
        return Response(result)
