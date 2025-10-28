from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from .models import Assignment
from teachers.models import StreamNotification  # adjust if in another app

def publish_scheduled_assignments():
    now = timezone.now()
    assignments = Assignment.objects.filter(status="scheduled", scheduled_for__lte=now)
    for assignment in assignments:
        assignment.status = "assigned"
        assignment.save()

        # ✅ Create notifications once published
        teacher = assignment.class_obj.teacher
        StreamNotification.objects.create(
            user=teacher,
            class_obj=assignment.class_obj,
            assignment=assignment,
            message=f"Your scheduled assignment '{assignment.title}' has been published."
        )

        for student in assignment.class_obj.students.all():
            StreamNotification.objects.create(
                user=student,
                class_obj=assignment.class_obj,
                assignment=assignment,
                message=f"New scheduled assignment '{assignment.title}' is now available!"
            )

        print(f"✅ Published scheduled assignment: {assignment.title}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(publish_scheduled_assignments, 'interval', minutes=1)
    scheduler.start()
