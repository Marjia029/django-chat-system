from django.db import models
from django.conf import settings
import os

def message_file_upload_path(instance, filename):
    """Generate upload path for message files"""
    return f'chat_files/{instance.sender.id}/{filename}'

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File'),
    ]
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    content = models.TextField(blank=True)  # Make content optional for media messages
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    
    # File fields
    file = models.FileField(upload_to=message_file_upload_path, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)  # in bytes
    file_type = models.CharField(max_length=100, blank=True, null=True)  # MIME type
    
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_encrypted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.get_message_type_display()}"
    
    def delete(self, *args, **kwargs):
        # Delete the file when the message is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)