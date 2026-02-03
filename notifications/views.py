from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    """
    GET: List all notifications for the authenticated user
    Automatically marks notifications as seen when fetched
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get all notifications for the user
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        #Unseen notifications
        unseen_notifications = notifications.filter(is_seen=False)
        unseen_count = unseen_notifications.count()
        
        # Mark all unseen notifications as seen in a single query
        unseen_notifications.update(is_seen=True)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            'notifications': serializer.data,
            'count': unseen_count
        })


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.is_read = True
            notification.save()
            return Response({'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'message': 'All notifications marked as read'})
