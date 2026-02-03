import json
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from .models import Message
from notifications.models import Notification

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Redis client for tracking open chats (per-user set)
        self.redis = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

        self.room_name = f'user_{self.user.id}'
        self.room_group_name = f'chat_{self.room_name}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            recipient_id = data.get('recipient_id')
            content = data.get('content')
            
            # Save message to database
            message = await self.save_message(recipient_id, content)
            
            if message:
                # Send message to sender
                await self.send(text_data=json.dumps({
                    'type': 'chat_message',
                    'message': {
                        'id': message.id,
                        'sender_id': message.sender.id,
                        'sender_email': message.sender.email,
                        'recipient_id': message.recipient.id,
                        'content': message.content,
                        'timestamp': message.timestamp.isoformat(),
                    }
                }))
                
                # Send message to recipient
                await self.channel_layer.group_send(
                    f'chat_user_{recipient_id}',
                    {
                        'type': 'chat_message_handler',
                        'message': {
                            'id': message.id,
                            'sender_id': message.sender.id,
                            'sender_email': message.sender.email,
                            'recipient_id': message.recipient.id,
                            'content': message.content,
                            'timestamp': message.timestamp.isoformat(),
                        }
                    }
                )
        elif message_type == 'open_chat':
            other_id = data.get('chat_with')
            if other_id:
                # Add to Redis set
                await sync_to_async(self.redis.sadd)(f'open_chats:{self.user.id}', other_id)
                # Mark related notifications as seen/read
                await self.mark_notifications_seen(other_id)
                await self.send(text_data=json.dumps({'type': 'open_chat_ack', 'chat_with': other_id}))
        elif message_type == 'close_chat':
            other_id = data.get('chat_with')
            if other_id:
                await sync_to_async(self.redis.srem)(f'open_chats:{self.user.id}', other_id)
                await self.send(text_data=json.dumps({'type': 'close_chat_ack', 'chat_with': other_id}))
    
    async def chat_message_handler(self, event):
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))
    
    async def notification_handler(self, event):
        notification = event['notification']
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': notification
        }))
    
    @database_sync_to_async
    def save_message(self, recipient_id, content):
        try:
            recipient = User.objects.get(id=recipient_id)
            message = Message.objects.create(
                sender=self.user,
                recipient=recipient,
                content=content
            )
            return message
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def mark_notifications_seen(self, other_id):
        Notification.objects.filter(
            user=self.user,
            related_message__sender_id=other_id,
            is_seen=False
        ).update(is_seen=True, is_read=True)