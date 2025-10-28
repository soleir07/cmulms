from django.apps import AppConfig


class TeachersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'teachers'

    def ready(self):
        import teachers.signals  # 👈 import signals when app is ready

    def ready(self):
        from .tasks import start_scheduler
        start_scheduler()