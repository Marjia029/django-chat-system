import json
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import base64
from .models import Message
from .encryption import encrypt_message, decrypt_message
from notifications.models import Notification

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------ #
    #  Connection lifecycle                                                #
    # ------------------------------------------------------------------ #

    async def connect(self):
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        # Redis client for tracking which chats are currently open (per-user set)
        self.redis = redis.Redis(
            host='127.0.0.1', port=6379, db=0, decode_responses=True
        )
        self.room_name = f'user_{self.user.id}'
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    # ------------------------------------------------------------------ #
    #  Incoming WebSocket messages                                         #
    # ------------------------------------------------------------------ #

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'chat_message':
            recipient_id = data.get('recipient_id')
            content = data.get('content', '')
            msg_type = data.get('message_type', 'text')

            # File-related fields (present only for media messages)
            file_data = data.get('file_data')    # base64 data-URI string
            file_name = data.get('file_name')    # original filename for display
            file_type = data.get('file_type')    # MIME type

            message = await self.save_message(
                recipient_id,
                content,
                msg_type,
                file_data,
                file_name,
                file_type,
            )

            if message:
                message_data = await self.serialize_message(message)

                # Echo back to the sender
                await self.send(text_data=json.dumps({
                    'type': 'chat_message',
                    'message': message_data,
                }))

                # Forward to the recipient's channel group
                await self.channel_layer.group_send(
                    f'chat_user_{recipient_id}',
                    {
                        'type': 'chat_message_handler',
                        'message': message_data,
                    }
                )

        elif message_type == 'open_chat':
            other_id = data.get('chat_with')
            if other_id:
                await sync_to_async(self.redis.sadd)(
                    f'open_chats:{self.user.id}', other_id
                )
                await self.mark_notifications_seen(other_id)
                await self.send(text_data=json.dumps({
                    'type': 'open_chat_ack',
                    'chat_with': other_id,
                }))

        elif message_type == 'close_chat':
            other_id = data.get('chat_with')
            if other_id:
                await sync_to_async(self.redis.srem)(
                    f'open_chats:{self.user.id}', other_id
                )
                await self.send(text_data=json.dumps({
                    'type': 'close_chat_ack',
                    'chat_with': other_id,
                }))

    # ------------------------------------------------------------------ #
    #  Channel-layer event handlers                                        #
    # ------------------------------------------------------------------ #

    async def chat_message_handler(self, event):
        """Relay a chat message received from the channel layer to the WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
        }))

    async def notification_handler(self, event):
        """Relay a notification received from the channel layer to the WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification'],
        }))

    # ------------------------------------------------------------------ #
    #  Database helpers                                                    #
    # ------------------------------------------------------------------ #

    @database_sync_to_async
    def save_message(
        self,
        recipient_id,
        content,
        msg_type,
        file_data,
        file_name,
        file_type,
    ):
        """
        Persist a message to the database.

        Text content is encrypted with Fernet before being stored.
        File uploads are decoded from their base64 data-URI; the actual file
        path on disk is automatically slugified via the model's upload_to function.
        The original filename is preserved in file_name for display purposes.
        """
        try:
            recipient = User.objects.get(id=recipient_id)

            # ---- Determine is_read via Redis --------------------------------
            is_read = False
            try:
                r = redis.Redis(
                    host='127.0.0.1', port=6379, db=0, decode_responses=True
                )
                if r.sismember(f'open_chats:{recipient_id}', self.user.id):
                    is_read = True
            except Exception as e:
                print(f"Redis check failed: {e}")

            # ---- Encrypt text content before storing -----------------------
            # encrypt_message() is a no-op for empty strings (media-only msgs).
            encrypted_content = encrypt_message(content)

            message_data = {
                'sender': self.user,
                'recipient': recipient,
                'content': encrypted_content,
                'message_type': msg_type,
                'is_read': is_read,
            }

            # ---- Handle optional file attachment ----------------------------
            if file_data and file_name:
                # file_data is a data-URI:  "data:<mime>;base64,<payload>"
                _header, filestr = file_data.split(';base64,')
                decoded_bytes = base64.b64decode(filestr)

                # ContentFile name is passed to message_file_upload_path which
                # slugifies it automatically — so the stored path is clean.
                # We keep the original file_name for display in the UI.
                file_content = ContentFile(decoded_bytes, name=file_name)

                message_data['file'] = file_content
                message_data['file_name'] = file_name          # original name, for UI
                message_data['file_type'] = file_type
                message_data['file_size'] = len(decoded_bytes)

            message = Message.objects.create(**message_data)
            return message

        except User.DoesNotExist:
            return None
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def serialize_message(self, message):
        """
        Serialize a Message instance into a plain dict for JSON transport.

        The stored ciphertext is decrypted back to plaintext here so the
        client always receives readable content.
        """
        from django.conf import settings as django_settings

        file_url = None
        if message.file:
            domain = "http://127.0.0.1:8000"
            file_url = f"{domain}{django_settings.MEDIA_URL}{message.file.name}"

        return {
            'id': message.id,
            'sender_id': message.sender.id,
            'sender_email': message.sender.email,
            'recipient_id': message.recipient.id,
            'content': decrypt_message(message.content),
            'message_type': message.message_type,
            'file_url': file_url,
            'file_name': message.file_name,   # original display name
            'file_size': message.file_size,
            'file_type': message.file_type,
            'timestamp': message.timestamp.isoformat(),
            'is_read': message.is_read,
        }

    @database_sync_to_async
    def mark_notifications_seen(self, other_id):
        Notification.objects.filter(
            user=self.user,
            related_message__sender_id=other_id,
            is_seen=False,
        ).update(is_seen=True, is_read=True)