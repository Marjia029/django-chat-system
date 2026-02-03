from rest_framework import serializers
from .models import Message
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_email', 'recipient', 'recipient_email', 
                  'content', 'timestamp', 'is_read']
        read_only_fields = ['sender', 'timestamp']


class ConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    user_username = serializers.CharField()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()
    unread_count = serializers.IntegerField()