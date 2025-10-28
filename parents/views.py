from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from teachers.models import Parent, Event, Announcement, StudentAnswer, Message, Quiz # Import Quiz model
from students.models import StudentQuizAttempt # Import StudentQuizAttempt
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, F, FloatField, ExpressionWrapper, Q # Import Q for filtering
import datetime # Import datetime for timedelta

User = get_user_model()

User = get_user_model()

@login_required
def dashboard(request):
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, "You are not linked as a parent. Please contact a teacher.")
        return redirect("index")

    # ✅ Get linked students only
    students = parent.students.all()

    return render(request, "parents/dashboard.html", {
        "parent": parent,
        "students": students,
    })


from types import SimpleNamespace

@login_required
def student_progress(request, student_id):
    student = get_object_or_404(User, id=student_id)
    parent = request.user.parent_profile

    # 🔒 Ensure parent is linked to the student
    if not parent.students.filter(id=student.id).exists():
        messages.error(request, "You are not authorized to view this student's progress.")
        return redirect("parents:dashboard")

    # ✅ Get related data safely
    classes = student.enrolled_classes.all() if hasattr(student, "enrolled_classes") else []
    submissions = getattr(student, "submissions", student.submission_set).all()

    # ✅ Get quiz attempts with scores and timestamps
    quiz_attempts = (
        StudentQuizAttempt.objects.filter(student=student)
        .select_related('quiz__class_obj__teacher') # Prefetch related data
        .annotate(
            total_score=Sum('quiz__answers__score', filter=Q(quiz__answers__student=student), output_field=FloatField()),
            quiz_created_at=F('quiz__created_at'),
            attempt_start_time=F('start_time'),
            attempt_submitted_at=F('submitted_at'),
            quiz_duration=F('quiz__duration')
        )
        .order_by('quiz__title')
    )

    quizzes_for_template = []
    for attempt in quiz_attempts:
        quiz_data = {
            'quiz__id': attempt.quiz.id,
            'quiz__title': attempt.quiz.title,
            'quiz__created_at': attempt.quiz_created_at,
            'quiz__class_obj__teacher__first_name': attempt.quiz.class_obj.teacher.first_name,
            'quiz__class_obj__teacher__last_name': attempt.quiz.class_obj.teacher.last_name,
            'display_score': attempt.total_score if attempt.total_score is not None else 0,
            'attempt__start_time': attempt.attempt_start_time,
            'attempt__submitted_at': attempt.attempt_submitted_at,
            'quiz__duration': attempt.quiz_duration,
        }
        # Calculate quiz end time for display
        if attempt.attempt_start_time and attempt.quiz_duration:
            quiz_data['attempt__end_time'] = attempt.attempt_start_time + datetime.timedelta(minutes=attempt.quiz_duration)
        else:
            quiz_data['attempt__end_time'] = None
        
        quizzes_for_template.append(SimpleNamespace(**quiz_data))

    # ✅ Filter type handling
    filter_type = request.GET.get("filter", "all")
    if filter_type == "with_grade":
        submissions = submissions.filter(grade__isnull=False)
    elif filter_type == "missing":
        submissions = submissions.filter(file="")

    # ✅ Ensure missing grades show as 0
    for submission in submissions:
        submission.display_grade = submission.grade if submission.grade is not None else 0

    return render(request, "parents/student_progress.html", {
        "student": student,
        "classes": classes,
        "submissions": submissions,
        "quizzes": quizzes_for_template,  # Now dot-accessible in template
        "parent": parent,
        "filter": filter_type,
    })


@login_required
def calendar(request):
    events = Event.objects.all().order_by("date")
    return render(request, "parents/calendar.html", {
        "events": events,
        })

@login_required
def announcements(request):
    # show all announcements (or filter later if needed)
    announcements = Announcement.objects.all().order_by('-date_posted')
    
    return render(request, "parents/announcements.html", {
        "announcements": announcements,
    })

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import get_user_model
from teachers.models import Class  # make sure this import is correct

User = get_user_model()

# -------------------------------
# 📩 MESSAGES INBOX
# -------------------------------
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import User
from teachers.models import Class
from teachers.models import Message
from teachers.models import ParentInvite


@login_required
def messages_inbox(request):
    user = request.user
    enrolled_classes = getattr(user, 'enrolled_classes', Class.objects.none()).filter(is_archived=False)

    # ✅ Determine contacts based on role
    if user.role == 'teacher':
        contacts = User.objects.filter(
            enrolled_classes__in=user.created_classes.filter(is_archived=False)
        ).distinct().exclude(id=user.id)

    elif user.role == 'student':
        teacher_ids = enrolled_classes.values_list('teacher', flat=True).distinct()
        contacts = User.objects.filter(id__in=teacher_ids)

    elif user.role == 'parent':
        # ✅ Handle multiple children linked to the parent
        parent_invites = ParentInvite.objects.filter(
            parent_email=user.email,
            accepted=True
        )

        if parent_invites.exists():
            # Get all students linked to this parent
            students = [invite.student for invite in parent_invites]

            # Collect all teacher IDs from the classes of these students
            teacher_ids = Class.objects.filter(
                enrollment__student__in=students,
                is_archived=False
            ).values_list('teacher_id', flat=True).distinct()

            contacts = User.objects.filter(
                Q(id__in=teacher_ids) | Q(id__in=[s.id for s in students])
            ).distinct().exclude(id=user.id)
        else:
            contacts = User.objects.none()

    else:
        contacts = User.objects.none()

    context = {
        'contacts': contacts,
        'other_user': None,
        'messages': [],
        'classes': getattr(user, 'created_classes', Class.objects.none()).all(),
        'enrolled_classes': enrolled_classes
    }
    return render(request, 'parents/conversation.html', context)


# -------------------------------
# 💬 CONVERSATION VIEW
# -------------------------------
@login_required
def conversation(request, user_id=None):
    user = request.user
    enrolled_classes = getattr(user, 'enrolled_classes', Class.objects.none()).filter(is_archived=False)

    if user.role == 'teacher':
        contacts = User.objects.filter(
            enrolled_classes__in=user.created_classes.filter(is_archived=False)
        ).distinct().exclude(id=user.id)

    elif user.role == 'student':
        teacher_ids = enrolled_classes.values_list('teacher', flat=True).distinct()
        contacts = User.objects.filter(id__in=teacher_ids)

    elif user.role == 'parent':
        # ✅ Multiple children support
        parent_invites = ParentInvite.objects.filter(
            parent_email=user.email,
            accepted=True
        )

        if parent_invites.exists():
            students = [invite.student for invite in parent_invites]
            teacher_ids = Class.objects.filter(
                enrollment__student__in=students,
                is_archived=False
            ).values_list('teacher_id', flat=True).distinct()

            contacts = User.objects.filter(
                Q(id__in=teacher_ids) | Q(id__in=[s.id for s in students])
            ).distinct().exclude(id=user.id)
        else:
            contacts = User.objects.none()
    else:
        contacts = User.objects.none()

    # ✅ Load selected chat
    other_user = None
    messages = []
    if user_id:
        other_user = get_object_or_404(User, id=user_id)
        messages = Message.objects.filter(
            Q(sender=user, recipient=other_user) |
            Q(sender=other_user, recipient=user)
        ).order_by('timestamp')

    # ✅ Send message
    if request.method == 'POST' and other_user:
        content = request.POST.get('content')
        if content.strip():
            Message.objects.create(sender=user, recipient=other_user, content=content)
            return redirect('parents:conversation', user_id=other_user.id)

    context = {
        'contacts': contacts,
        'other_user': other_user,
        'messages': messages,
        'enrolled_classes': enrolled_classes
    }
    return render(request, 'parents/conversation.html', context)

