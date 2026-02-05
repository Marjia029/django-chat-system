from rest_framework import serializers
from .models import Message
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    recipient_id = serializers.IntegerField(source='recipient.id', read_only=True)
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id',
            'sender_id',
            'sender_email',
            'recipient_id',
            'recipient_email',
            'content',
            'timestamp',
            'is_read',
        ]
        read_only_fields = [
            'id',
            'sender_id',
            'sender_email',
            'recipient_id',
            'recipient_email',
            'timestamp',
            'is_read',
        ]




class ConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    user_username = serializers.CharField()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()
    unread_count = serializers.IntegerField()