from django.db import models
from django.conf import settings
import string, random
from django.contrib.auth.models import User


def generate_class_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Class(models.Model):
    class_name = models.CharField(max_length=100)
    subject_name = models.CharField(max_length=100)
    section = models.CharField(max_length=50)
    time = models.TimeField(null=True, blank=True)

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_classes"
    )
    code = models.CharField(max_length=10, unique=True, default=generate_class_code)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="enrolled_classes",
        blank=True
    )
    is_archived = models.BooleanField(default=False)  # ✅ new field
    banner = models.ImageField(upload_to="class_banners/", blank=True, null=True)
    # ✅ Replace theme image with a banner color
    banner_color = models.CharField(max_length=7, default="#ffffff", help_text="HTML color code like #3498db")

    # ✅ Add Google Drive folder link
    drive_folder_link = models.URLField(blank=True, null=True)

    def get_banner_url(self):
        """
        Returns the appropriate banner — if an image exists, use it;
        otherwise use the selected banner color.
        """
        if self.banner:
            return self.banner.url
        return self.banner_color  # this will be used as background color
    def __str__(self):
        return f"{self.class_name} - {self.section}"
    
import json
import os
from django.utils import timezone

class Assignment(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    points = models.IntegerField(default=100)
    due_date = models.DateTimeField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ Who this assignment is for
    assigned_to = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="student_assignments", blank=True)

    # ✅ NEW FIELDS
    status = models.CharField(
        max_length=20,
        choices=[("draft", "Draft"), ("assigned", "Assigned"), ("scheduled", "Scheduled")],
        default="assigned"
    )
    scheduled_for = models.DateTimeField(null=True, blank=True)

    def is_ready_to_publish(self):
        return self.status == "scheduled" and self.scheduled_for and self.scheduled_for <= timezone.now()

    def __str__(self):
        return f"{self.title} ({self.class_obj.class_name} - {self.class_obj.section})"

class AssignmentAttachment(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="assignments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def __str__(self):
        return self.filename

class AssignmentLink(models.Model):
    assignment = models.ForeignKey(
        'Assignment', 
        on_delete=models.CASCADE, 
        related_name='links'
    )
    url = models.URLField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f"Link for {self.assignment.title} - {self.url}"
import urllib.parse

class AssignmentVideo(models.Model):
    assignment = models.ForeignKey(Assignment, related_name="videos", on_delete=models.CASCADE)
    url = models.URLField()
    video_id = models.CharField(max_length=20, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    author_name = models.CharField(max_length=255, blank=True, null=True)
    thumbnail_url = models.URLField(blank=True, null=True)
    embed_html = models.TextField(blank=True, null=True)  # you can render this directly
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def video_id(self):
        """
        Extracts the YouTube video ID from different formats of URLs.
        """
        parsed_url = urllib.parse.urlparse(self.url)
        if parsed_url.hostname in ["youtu.be"]:
            return parsed_url.path.lstrip("/")
        if parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
            query = urllib.parse.parse_qs(parsed_url.query)
            return query.get("v", [None])[0]
        return None
    
    def __str__(self):
        return self.title or self.url

    def save(self, *args, **kwargs):
        # Optional: fetch metadata on save if missing (uses utils.fetch_youtube_metadata)
        if not (self.title and self.embed_html):
            try:
                from .utils import fetch_youtube_metadata, extract_video_id
                meta = fetch_youtube_metadata(self.url)
                if meta:
                    self.video_id = extract_video_id(self.url)
                    self.title = meta.get("title")
                    self.author_name = meta.get("author_name")
                    self.thumbnail_url = meta.get("thumbnail_url")
                    self.embed_html = meta.get("html")
            except Exception:
                pass
        super().save(*args, **kwargs)

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to="submissions/")
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_submitted = models.BooleanField(default=False)
    grade = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    is_published = models.BooleanField(default=False)
    is_returned = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=[
            ("assigned", "Assigned"),
            ("turned_in", "Turned In"),
            ("missing", "Missing"),
        ],
        default="assigned",
    )

    def get_status_display_value(self):
        """Convenience method for showing dynamic status."""
        if self.grade is not None:
            return "Graded"
        if self.file:
            return "Turned In"
        return "Missing"

    def __str__(self):
        return f"{self.student.username} → {self.assignment.title}"

class StreamNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    class_obj = models.ForeignKey(
        "Class",
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    attendance_session = models.ForeignKey(
        "AttendanceSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    assignment = models.ForeignKey("Assignment", on_delete=models.CASCADE, null=True, blank=True)
    quiz= models.ForeignKey("Quiz", on_delete=models.CASCADE, null=True, blank=True)  # NEW field
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)  # ✅ New field
    
     # 🆕 New fields for scheduling
    scheduled = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user} - {self.message[:30]}"
    
class Announcement(models.Model):
    CATEGORY_CHOICES = [
        ('exam', 'Exams'),
        ('event', 'Events'),
        ('reminder', 'Reminders'),
        ('general', 'General'),
    ]
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    date_posted = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    def __str__(self):
        return self.title
    
class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    EVENT_TYPE_CHOICES = [
        ("announcement", "Announcement"),
        ("exam", "Exam"),
        ("holiday", "Holiday"),
        ("meeting", "Meeting"),
    ]
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default="announcement")

    def __str__(self):
        return f"{self.title} ({self.date})"
    
class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sent_messages",
        on_delete=models.CASCADE
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="received_messages",
        on_delete=models.CASCADE
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"From {self.sender} to {self.recipient}: {self.content[:20]}"

class Quiz(models.Model):
    QUIZ_TYPES = [
        ("quiz", "Quiz"),
        ("exam", "Exam"),
    ]
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField(max_length=255)
    quiz_type = models.CharField(max_length=10, choices=QUIZ_TYPES, default="quiz")
    description = models.TextField(blank=True, null=True)
    duration = models.PositiveIntegerField(help_text="Duration in minutes",null=True,blank=True)  # teacher sets this
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_quizzes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_quiz_type_display()})"


class Question(models.Model):
    QUESTION_TYPES = [
        ("multiple-choice", "Multiple Choice"),
        ("identification", "Identification"),
        ("essay", "Essay"),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)

    def __str__(self):
        return f"{self.text[:50]}..."


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"


class StudentAnswer(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_answers"
    )
    quiz = models.ForeignKey(Quiz, null=True, blank=True, on_delete=models.CASCADE, related_name="answers")  # ✅ Add this
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    selected_option = models.ForeignKey(
        Option, null=True, blank=True, on_delete=models.SET_NULL
    )
    text_answer = models.TextField(blank=True, null=True)  # for essay/identification
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.FloatField(default=0)  # auto-grading result
    
    def __str__(self):
        return f"Answer by {self.student} → {self.question.text[:30]}"
    
import uuid

class ParentInvite(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="parent_invites"
    )
    parent_email = models.EmailField()
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_parent_invites"
    )
    accepted = models.BooleanField(default=False)

    # ✅ Use UUID but no unique=True (safer migrations)
    token = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite for {self.parent_email} to {self.student.username}"
    

class Parent(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_profile"
    )
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="linked_parents",
        blank=True
    )

    def __str__(self):
        return f"Parent: {self.user.get_full_name() or self.user.username}"

class ClassComment(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="class_comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Class comment by {self.user.username} on {self.assignment.title}"

class PrivateComment(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="private_comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_private_comments")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_private_comments", null=True, blank=True) # New field
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Private comment by {self.user.username} on {self.assignment.title}"
    
from django.utils import timezone

class AttendanceSession(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="attendance_sessions")
    teacher = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name="created_sessions",
    null=True,
    blank=True
)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    radius_m = models.FloatField(default=50)  # default classroom radius in meters
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)  # optional end
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session for {self.class_obj} at {self.start_time.strftime('%H:%M')}"

class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status_choices = [("present", "Present"), ("absent", "Absent")]
    status = models.CharField(max_length=10, choices=status_choices, default="absent")
    check_in_time = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    distance_from_class = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ("session", "student")

    def __str__(self):
        return f"{self.student.username} - {self.status}"
