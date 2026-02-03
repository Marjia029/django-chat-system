import redis
from django.test import TestCase
from django.contrib.auth import get_user_model
from chat.models import Message
from .models import Notification

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        self.r = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
        self.r.flushdb()

        # Create two users
        self.sender = User.objects.create_user(email='sender@example.com', password='pass')
        self.recipient = User.objects.create_user(email='recipient@example.com', password='pass')

    def test_suppressed_when_chat_open(self):
        # Recipient has an open chat with sender
        self.r.sadd(f'open_chats:{self.recipient.id}', self.sender.id)

        # Create a message from sender to recipient
        Message.objects.create(sender=self.sender, recipient=self.recipient, content='hi')

        # No notification should be created
        self.assertFalse(Notification.objects.filter(user=self.recipient).exists())

    def test_created_when_chat_closed(self):
        Message.objects.create(sender=self.sender, recipient=self.recipient, content='hello')
        self.assertTrue(Notification.objects.filter(user=self.recipient, notification_type='message').exists())
