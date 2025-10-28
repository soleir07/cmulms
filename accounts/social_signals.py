from allauth.account.signals import user_signed_up, user_logged_in
from django.dispatch import receiver
from .models import Profile

@receiver(user_signed_up)
@receiver(user_logged_in)
def update_google_avatar(request, user, **kwargs):
    """
    Automatically updates avatar_url when a user logs in with Google.
    """
    try:
        # Get their social login account
        social_account = user.socialaccount_set.filter(provider='google').first()
        if social_account:
            # Get Google profile picture
            avatar_url = social_account.extra_data.get('picture')

            profile, created = Profile.objects.get_or_create(user=user)
            if avatar_url:
                profile.avatar_url = avatar_url
                profile.save()
    except Exception as e:
        print("Error syncing Google avatar:", e)