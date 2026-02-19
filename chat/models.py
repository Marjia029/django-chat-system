from django.db import models
from django.conf import settings
import os
import re
import uuid


def slugify_filename(filename: str) -> str:
    """
    Convert a filename into a URL-friendly slug while preserving the extension.
    Appends a short UUID to guarantee uniqueness even for identical filenames.

    Example:
        'My Photo (1).PNG'  ->  'my-photo-1-3f9a2b1c.png'
    """
    name, ext = os.path.splitext(filename)

    # Lowercase everything
    name = name.lower()

    # Remove characters that are not alphanumeric, spaces, or hyphens
    name = re.sub(r'[^\w\s-]', '', name)

    # Replace whitespace and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)

    # Collapse multiple hyphens into one and strip leading/trailing hyphens
    name = re.sub(r'-+', '-', name).strip('-')

    # Fallback if the name becomes empty after sanitization
    if not name:
        name = 'file'

    # Append 8-char UUID hex for uniqueness
    unique_id = uuid.uuid4().hex[:8]

    return f"{name}-{unique_id}{ext.lower()}"


def message_file_upload_path(instance, filename: str) -> str:
    """
    Upload path: chat_files/<sender_id>/<slugified_filename>
    Example:     chat_files/42/holiday-photo-3f9a2b1c.jpg
    """
    clean_name = slugify_filename(filename)
    return f'chat_files/{instance.sender.id}/{clean_name}'


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

    # Stores Fernet-encrypted ciphertext for text messages.
    # Left blank for pure media messages.
    content = models.TextField(blank=True)

    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPES,
        default='text'
    )

    # File fields — the upload path now uses slugify_filename automatically
    file = models.FileField(
        upload_to=message_file_upload_path,
        blank=True,
        null=True
    )
    # Stores the original filename for display purposes (not the slugified path)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)   # bytes
    file_type = models.CharField(max_length=100, blank=True, null=True)  # MIME type

    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.get_message_type_display()}"

    def delete(self, *args, **kwargs):
        """Delete the associated file from disk when the message is deleted."""
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)