from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'notification_type', 'message', 'is_read', 'is_seen', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_seen', 'created_at')
    search_fields = ('user__email', 'user__username', 'message')
    readonly_fields = ('created_at', 'id')
    fieldsets = (
        ('Notification Info', {
            'fields': ('id', 'user', 'notification_type', 'message', 'related_message')
        }),
        ('Status', {
            'fields': ('is_read', 'is_seen')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
