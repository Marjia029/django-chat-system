from rest_framework import serializers
from .models import Message
from .encryption import decrypt_message
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    recipient_id = serializers.IntegerField(source='recipient.id', read_only=True)
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    file_url = serializers.SerializerMethodField()

    # Exposes decrypted content instead of the raw ciphertext stored in the DB.
    # The field is named 'content' so the frontend requires zero changes.
    content = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'sender_id',
            'sender_email',
            'recipient_id',
            'recipient_email',
            'content',          # decrypted via get_content()
            'message_type',
            'file',
            'file_url',
            'file_name',        # original display name
            'file_size',
            'file_type',
            'timestamp',
            'is_read',
        ]
        read_only_fields = [
            'id',
            'sender_id',
            'sender_email',
            'recipient_id',
            'recipient_email',
            'content',
            'timestamp',
            'is_read',
        ]

    def get_content(self, obj):
        """
        Decrypt the stored ciphertext before returning it to the client.
        Falls back gracefully to the raw value for any legacy unencrypted rows.
        """
        return decrypt_message(obj.content)

    def get_file_url(self, obj):
        """Build an absolute URL for the stored file, if present."""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class ConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    user_username = serializers.CharField()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()
    unread_count = serializers.IntegerField()
    last_message_type = serializers.CharField()