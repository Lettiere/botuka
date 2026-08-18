from django.urls import path

from .consumers import SocialConversationConsumer


websocket_urlpatterns = [
    path(
        "ws/social/mensagens/<uuid:uuid>/",
        SocialConversationConsumer.as_asgi(),
        name="social_conversation_ws",
    ),
]
