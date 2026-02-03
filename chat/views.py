from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Max, Count, Case, When
from django.contrib.auth import get_user_model
from .models import Message
from .serializers import MessageSerializer, ConversationSerializer

User = get_user_model()


class SendMessageView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        recipient_id = request.data.get('recipient')
        content = request.data.get('content')
        
        if not recipient_id or not content:
            return Response(
                {'error': 'Recipient and content are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            recipient = User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Recipient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=content
        )
        
        serializer = self.get_serializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]
    
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
            
            conversation_list.append({
                'user_id': other_user.id,
                'user_email': other_user.email,
                'user_username': other_user.username,
                'last_message': last_message.content if last_message else '',
                'last_message_time': last_message.timestamp if last_message else None,
                'unread_count': unread_count
            })
        
        serializer = ConversationSerializer(conversation_list, many=True)
        return Response(serializer.data)


class MessageHistoryView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        other_user_id = self.kwargs.get('user_id')
        
        # Mark messages as read
        Message.objects.filter(
            sender_id=other_user_id,
            recipient=user,
            is_read=False
        ).update(is_read=True)
        
        return Message.objects.filter(
            Q(sender=user, recipient_id=other_user_id) |
            Q(sender_id=other_user_id, recipient=user)
        ).order_by('timestamp')