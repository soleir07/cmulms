from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime
from teachers.models import Quiz   # import your Quiz model

class StudentQuizAttempt(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, related_name="attempts", on_delete=models.CASCADE)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("expired", "Expired"),
        ],
        default="in_progress"
    )
    start_time = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("student", "quiz")  # one attempt per student

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} ({self.status})"

    def end_time(self):
        """When this student’s attempt should close"""
        return self.start_time + datetime.timedelta(minutes=self.quiz.duration)

    def is_active(self):
        """Check if student can still answer"""
        return timezone.now() < self.end_time() and self.status == "in_progress"

    def time_remaining(self):
        """Seconds left for this student"""
        remaining = self.end_time() - timezone.now()
        return max(0, int(remaining.total_seconds()))
