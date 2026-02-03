from django.urls import path
from .views import SendMessageView, ConversationListView, MessageHistoryView

urlpatterns = [
    path('send/', SendMessageView.as_view(), name='send-message'),
    path('conversations/', ConversationListView.as_view(), name='conversations'),
    path('history/<int:user_id>/', MessageHistoryView.as_view(), name='message-history'),
]