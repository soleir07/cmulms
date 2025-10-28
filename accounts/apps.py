# accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        import accounts.signals
        import accounts.social_signals  # <-- Add this line
