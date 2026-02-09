import json
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import base64
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
            content = data.get('content', '')
            msg_type = data.get('message_type', 'text')
            
            # Handle file data if present
            file_data = data.get('file_data')
            file_name = data.get('file_name')
            file_type = data.get('file_type')
            
            # Save message to database
            message = await self.save_message(
                recipient_id, 
                content, 
                msg_type,
                file_data,
                file_name,
                file_type
            )
            
            if message:
                message_data = await self.serialize_message(message)
                
                # Send message to sender
                await self.send(text_data=json.dumps({
                    'type': 'chat_message',
                    'message': message_data
                }))
                
                # Send message to recipient
                await self.channel_layer.group_send(
                    f'chat_user_{recipient_id}',
                    {
                        'type': 'chat_message_handler',
                        'message': message_data
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
    def save_message(self, recipient_id, content, msg_type, file_data, file_name, file_type):
        try:
            recipient = User.objects.get(id=recipient_id)
            is_read = False
            try:
                # Use a sync redis client here or reuse connection if thread-safe
                # Ideally, create a new sync client for this db thread or use django-redis
                r = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
                if r.sismember(f'open_chats:{recipient_id}', self.user.id):
                    is_read = True
            except Exception as e:
                print(f"Redis check failed: {e}")
            
            message_data = {
                'sender': self.user,
                'recipient': recipient,
                'content': content,
                'message_type': msg_type,
                'is_read': is_read
            }
            
            # Handle file if present
            if file_data and file_name:
                # Decode base64 file data
                format, filestr = file_data.split(';base64,')
                file_content = ContentFile(base64.b64decode(filestr), name=file_name)
                
                message_data['file'] = file_content
                message_data['file_name'] = file_name
                message_data['file_type'] = file_type
                message_data['file_size'] = len(base64.b64decode(filestr))
            
            message = Message.objects.create(**message_data)
            return message
        except User.DoesNotExist:
            return None
        except Exception as e:
            print(f"Error saving message: {e}")
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        from django.conf import settings
        
        file_url = None
        if message.file:
            # Build absolute URL for file
            domain = "http://127.0.0.1:8000"
            file_url = f"{domain}{settings.MEDIA_URL}{message.file.name}"
        
        return {
            'id': message.id,
            'sender_id': message.sender.id,
            'sender_email': message.sender.email,
            'recipient_id': message.recipient.id,
            'content': message.content,
            'message_type': message.message_type,
            'file_url': file_url,
            'file_name': message.file_name,
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
            is_seen=False
        ).update(is_seen=True, is_read=True)