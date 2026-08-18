import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from .models import SocialConversation

logger = logging.getLogger(__name__)


class SocialConversationConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):

        self.conversation_uuid = str(
            self.scope["url_route"]["kwargs"]["uuid"]
        )

        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        allowed = await self._user_can_access_conversation(
            user.pk,
            self.conversation_uuid,
        )

        if not allowed:
            await self.close(code=4403)
            return

        self.group_name = (
            f"social_conversation_{self.conversation_uuid.replace('-', '_')}"
        )

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json({
            "event": "connection.ready",
            "conversation": self.conversation_uuid,
        })

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)

        if group_name:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        event = content.get("event")

        if event == "ping":
            await self.send_json({
                "event": "pong",
            })

    async def chat_message(self, event):

        await self.send_json({
            "event": "message.created",
            "message": event["message"],
        })

    @database_sync_to_async
    def _user_can_access_conversation(
        self,
        user_id,
        conversation_uuid,
    ):
        return SocialConversation.objects.filter(
            uuid=conversation_uuid,
            ativo=True,
            participantes__pk=user_id,
        ).exists()
