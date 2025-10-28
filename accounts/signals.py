# accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings  # 👈 use this to get the AUTH_USER_MODEL
from .models import Profile, User  # your custom User
from teachers.models import Parent  # adjust path

@receiver(post_save, sender=User)  # 👈 now using your custom User
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)



# ✅ Google avatar signal
from allauth.account.signals import user_logged_in

@receiver(user_logged_in)
def save_google_avatar_once(request, user, **kwargs):
    social_account = user.socialaccount_set.filter(provider='google').first()
    if social_account:
        picture_url = social_account.extra_data.get('picture')
        if picture_url:
            profile, created = Profile.objects.get_or_create(user=user)
            if not profile.avatar:  # only save once
                profile.avatar = picture_url
                profile.save()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_parent_profile(sender, instance, created, **kwargs):
    if created and instance.role == "parent":
        Parent.objects.get_or_create(user=instance)
