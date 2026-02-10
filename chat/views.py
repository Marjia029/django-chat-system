from rest_framework import status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Max
from django.contrib.auth import get_user_model
from .models import Message
from .serializers import MessageSerializer, ConversationSerializer

User = get_user_model()
class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email']
    
    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication is required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        user = request.user
        
        # Get all users the current user has conversations with
        conversations = Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).values(
            'sender', 'recipient'
        ).annotate(
            last_message_time=Max('timestamp')
        ).order_by('-last_message_time')
        
        conversation_list = []
        seen_users = set()
        
        for conv in conversations:
            other_user_id = conv['recipient'] if conv['sender'] == user.id else conv['sender']
            
            if other_user_id in seen_users:
                continue
            
            seen_users.add(other_user_id)
            
            try:
                other_user = User.objects.get(id=other_user_id)
            except User.DoesNotExist:
                continue
            
            # Get last message
            last_message = Message.objects.filter(
                Q(sender=user, recipient=other_user) |
                Q(sender=other_user, recipient=user)
            ).order_by('-timestamp').first()
            
            # Count unread messages
            unread_count = Message.objects.filter(
                sender=other_user,
                recipient=user,
                is_read=False
            ).count()
            
            # Format last message content based on type
            last_message_content = ''
            last_message_type = 'text'
            if last_message:
                last_message_type = last_message.message_type
                if last_message.message_type == 'text':
                    last_message_content = last_message.content
                elif last_message.message_type == 'image':
                    last_message_content = '📷 Photo'
                elif last_message.message_type == 'video':
                    last_message_content = '🎥 Video'
                elif last_message.message_type == 'audio':
                    last_message_content = '🎵 Audio'
                elif last_message.message_type == 'file':
                    last_message_content = f'📎 {last_message.file_name or "File"}'
            
            conversation_list.append({
                'user_id': other_user.id,
                'user_email': other_user.email,
                'user_username': other_user.username,
                'last_message': last_message_content,
                'last_message_time': last_message.timestamp if last_message else None,
                'unread_count': unread_count,
                'last_message_type': last_message_type
            })
            
        paginator = PageNumberPagination()
        paginated_conversations = paginator.paginate_queryset(conversation_list, request)
        
        serializer = ConversationSerializer(paginated_conversations, many=True)
        return paginator.get_paginated_response(serializer.data)

class MessageHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, *args, **kwargs):
        user = request.user
        other_user_id = user_id

        # 1. Update logic: Mark incoming messages as read
        Message.objects.filter(
            sender_id=other_user_id,
            recipient=user,
            is_read=False
        ).update(is_read=True)

        # 2. Fetch logic: Get conversation history
        queryset = Message.objects.filter(
            Q(sender=user, recipient_id=other_user_id) |
            Q(sender_id=other_user_id, recipient=user)
        ).order_by('timestamp')

        # 3. Serialization logic
        # Note: We pass the request in context manually here
        serializer = MessageSerializer(
            queryset, 
            many=True, 
            context={'request': request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)