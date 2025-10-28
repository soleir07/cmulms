from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('parent', 'Parent'),
        ('admin', 'Admin'),
        ("school_admin", "School Admin"),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True,   # ✅ allow empty
        null=True     # ✅ allow NULL in DB
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
    
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)  # Local uploads
    avatar_url = models.URLField(blank=True, null=True)  # For Google or external URLs

    def __str__(self):
        return self.user.username

    @property
    def display_avatar(self):
        """Return either uploaded image or external URL."""
        if self.avatar:
            return self.avatar.url
        elif self.avatar_url:
            return self.avatar_url
        return None