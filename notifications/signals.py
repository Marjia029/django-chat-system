import redis
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.models import Message
from .models import Notification


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """
    Signal to automatically create a notification when a new message is sent,
    and push the notification to the recipient over Channels in real time.
    """
    if created:
        # If the recipient currently has an open chat with the sender, do not create/send a notification
        r = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
        if r.sismember(f'open_chats:{instance.recipient.id}', instance.sender.id):
            return

        notification = Notification.objects.create(
            user=instance.recipient,
            notification_type='message',
            message=f"New message from {instance.sender.username}",
            related_message=instance
        )

        channel_layer = get_channel_layer()
        payload = {
            'type': 'notification_handler',
            'notification': {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'message': notification.message,
                'is_read': notification.is_read,
                'is_seen': notification.is_seen,
                'created_at': notification.created_at.isoformat(),
                'related_message_id': instance.id,
            }
        }

        # Send after DB transaction commits to avoid race conditions
        def send_notification():
            async_to_sync(channel_layer.group_send)(
                f'chat_user_{instance.recipient.id}',
                payload
            )

        transaction.on_commit(send_notification)
