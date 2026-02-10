from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import UserProfile
from .serializers import (
    UserRegistrationSerializer,
    VerifyOTPSerializer,
    PasswordResetRequestSerializer,
    ResendOTPSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserProfileUpdateSerializer
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate and save OTP
        otp_code = user.generate_otp('registration')
        
        # Send OTP via email
        send_mail(
            'Verify Your Email',
            f'Your OTP code is: {otp_code}\n\nThis code will expire in 2 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        return Response(
            {
                "success": True,
                "status_code": 201,
                "message": "Registration successful. An OTP has been sent to your email for verification.",
                "data": {
                    "email": user.email
                }
            },
            status=status.HTTP_201_CREATED
        )


class VerifyOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data.get('purpose', 'registration')
        
        try:
            user = User.objects.get(email=email)
            
            # Verify OTP with provided purpose
            if not user.verify_otp(otp_code, purpose):
                return Response({
                    'error': 'Invalid or expired OTP'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark OTP as used
            user.mark_otp_used()
            
            # Update verification/activation based on purpose
            user.is_email_verified = True
            if purpose == 'registration':
                user.is_active = True
                user.save()
                return Response({
                    'message': 'Email verified successfully. You can now log in.'
                }, status=status.HTTP_200_OK)
            
            # For password reset, generate and return password reset token
            elif purpose == 'password_reset':
                user.save()
                password_reset_token = user.generate_password_reset_token()
                return Response({
                    'message': 'OTP verified successfully. Use the password reset token to change your password.',
                    'password_reset_token': password_reset_token
                }, status=status.HTTP_200_OK)
            
            user.save()
            return Response({
                'message': 'OTP verified successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ResendOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResendOTPSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        purpose = serializer.validated_data.get('purpose', 'registration')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate and save new OTP
            otp_code = user.generate_otp(purpose)
            
            # Send OTP via email
            if purpose == 'registration':
                subject = 'Verify Your Email'
                message = f'Your OTP code is: {otp_code}\n\nThis code will expire in 2 minutes.'
            elif purpose == 'password_reset':
                subject = 'Password Reset OTP'
                message = f'Your password reset OTP code is: {otp_code}\n\nThis code will expire in 2 minutes.'
            else:
                subject = 'Your OTP Code'
                message = f'Your OTP code is: {otp_code}\n\nThis code will expire in 2 minutes.'
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': f'OTP has been resent to your email',
                'email': user.email
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # For security, don't reveal if email exists or not
            return Response({
                'message': 'If this email exists in our system, an OTP has been resent'
            }, status=status.HTTP_200_OK)


class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate and save OTP
            otp_code = user.generate_otp('password_reset')
            
            # Send OTP via email
            send_mail(
                'Password Reset OTP',
                f'Your password reset OTP code is: {otp_code}\n\nThis code will expire in 2 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'OTP sent to your email'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # For security, don't reveal if email exists or not
            return Response({
                'message': 'If this email exists, an OTP has been sent'
            }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password_reset_token = serializer.validated_data['password_reset_token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            
            # Verify password reset token
            if not user.verify_password_reset_token(password_reset_token):
                return Response({
                    'error': 'Invalid or expired password reset token'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark password reset token as used
            user.mark_password_reset_token_used()
            
            # Reset password
            user.set_password(new_password)
            user.save()
            
            return Response({
                'message': 'Password reset successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        # Return all users except the current user
        return User.objects.filter(is_active=True, is_email_verified=True).exclude(id=self.request.user.id)


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user.profile
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return full user data with updated profile
        user_serializer = UserSerializer(request.user)
        return Response({
            'message': 'Profile updated successfully',
            'user': user_serializer.data
        })