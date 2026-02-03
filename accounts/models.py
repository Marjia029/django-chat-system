from django.contrib.auth.models import AbstractUser
from django.db import models
import random
from datetime import timedelta
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    
    # OTP fields
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_purpose = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        choices=[
            ('registration', 'Registration'),
            ('password_reset', 'Password Reset')
        ]
    )
    otp_created_at = models.DateTimeField(blank=True, null=True)
    otp_is_used = models.BooleanField(default=False)
    
    # Password Reset Token fields
    password_reset_token = models.CharField(max_length=32, blank=True, null=True)
    password_reset_token_created_at = models.DateTimeField(blank=True, null=True)
    password_reset_token_is_used = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def generate_otp(self, purpose):
        """Generate and save OTP for the user"""
        self.otp_code = str(random.randint(100000, 999999))
        self.otp_purpose = purpose
        self.otp_created_at = timezone.now()
        self.otp_is_used = False
        self.save()
        return self.otp_code
    
    def verify_otp(self, code, purpose):
        """Verify OTP code"""
        if not self.otp_code or not self.otp_created_at:
            return False
        
        # Check if OTP matches
        if self.otp_code != code:
            return False
        
        # Check if purpose matches
        if self.otp_purpose != purpose:
            return False
        
        # Check if already used
        if self.otp_is_used:
            return False
        
        # Check if expired (10 minutes)
        if timezone.now() > self.otp_created_at + timedelta(minutes=2):
            return False
        
        return True
    
    def mark_otp_used(self):
        """Mark OTP as used"""
        self.otp_is_used = True
        self.save()
    
    def generate_password_reset_token(self):
        """Generate and save password reset token"""
        import secrets
        self.password_reset_token = secrets.token_hex(16)
        self.password_reset_token_created_at = timezone.now()
        self.password_reset_token_is_used = False
        self.save()
        return self.password_reset_token
    
    def verify_password_reset_token(self, token):
        """Verify password reset token"""
        if not self.password_reset_token or not self.password_reset_token_created_at:
            return False
        
        # Check if token matches
        if self.password_reset_token != token:
            return False
        
        # Check if already used
        if self.password_reset_token_is_used:
            return False
        
        # Check if expired (10 minutes)
        if timezone.now() > self.password_reset_token_created_at + timedelta(minutes=10):
            return False
        
        return True
    
    def mark_password_reset_token_used(self):
        """Mark password reset token as used"""
        self.password_reset_token_is_used = True
        self.save()
    
    def __str__(self):
        return self.email


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email}'s Profile"