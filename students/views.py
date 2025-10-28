from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from teachers.models import Class  # import the teacher’s Class model
from .forms import JoinClassForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from teachers.models import Event,Assignment,Submission,Message,StreamNotification,PrivateComment,ClassComment
from django.views.decorators.cache import never_cache

@never_cache   
@login_required
def dashboard(request, class_id=None):
    user = request.user
    # All classes the student is enrolled in
    enrolled_classes = request.user.enrolled_classes.filter(is_archived=False)  # 👈 Only active classes
    # Optionally, you can show classes in grid (same as sidebar)
    classes = enrolled_classes.order_by('class_name')
    if class_id:
        # Get the class and verify the student belongs to it
        class_obj = get_object_or_404(Class, id=class_id, students=request.user)
        assignments = Assignment.objects.filter(class_obj=class_obj)
    else:
        # Default: show all assignments for all enrolled classes
        assignments = Assignment.objects.filter(class_obj__students=request.user)

    work_list = []
    for assignment in assignments.select_related("class_obj"):
        submission = Submission.objects.filter(
            assignment=assignment, student=request.user
        ).first()
        work_list.append({
            "assignment": assignment,
            "submission": submission,
        })

    return render(request, "students/dashboard.html", {
        "classes": classes,
        "enrolled_classes": enrolled_classes,
        "class_id": class_id,
    })

@login_required
def calendar(request):
    events = Event.objects.all().order_by("date")
    enrolled_classes = request.user.enrolled_classes.filter(is_archived=False)  # 👈 Only active classes
    return render(request, "students/calendar.html", {
        "events": events,
        "enrolled_classes": enrolled_classes
        })

@login_required
@require_POST
def join_class_ajax(request):
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        try:
            class_obj = Class.objects.get(code=code)
            class_obj.students.add(request.user)  # Save to DB
            class_obj.save()
            
            # Return updated info
            enrolled_count = request.user.enrolled_classes.count()
            return JsonResponse({
                "status": "success",
                "message": f"Successfully joined {class_obj.class_name}!",
                "class": {
                    "id": class_obj.id,
                    "name": class_obj.class_name,
                    "section": class_obj.section,
                    "banner": class_obj.get_banner_url(),
                },
                "class_count": enrolled_count
            })
        except Class.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid class code."})
    else:
        return JsonResponse({"status": "error", "message": "Form is invalid."})
    

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from teachers.models import Class, Quiz, Submission
from teachers.models import StreamNotification  # make sure this is imported
from django.db import models

@login_required
def class_detail(request, id):
    class_obj = get_object_or_404(Class, id=id, students=request.user)
    # ✅ Hide not-yet-scheduled assignments
    assignments = class_obj.assignments.filter(
        models.Q(status="assigned") |
        models.Q(status="scheduled", scheduled_for__lte=timezone.now())
    ).order_by('-created_at')
    user = request.user

    # ✅ FIX: Only get notifications for this user in this class
    notifications = StreamNotification.objects.filter(
        class_obj=class_obj,
        user=user
    ).order_by('-created_at')
    unread_count = StreamNotification.objects.filter(
        class_obj=class_obj,
        user=user,
        read=False
    ).count()

    # Get quizzes and attempts
    quizzes = Quiz.objects.filter(class_obj=class_obj).order_by("-created_at")
    for quiz in quizzes:
        quiz.student_attempt = quiz.attempts.filter(student=user).first()

    # Attach student's submission to each assignment
    for assignment in assignments:
        assignment.student_submission = Submission.objects.filter(
            assignment=assignment,
            student=user
        ).first()

    enrolled_classes = user.enrolled_classes.all()
    classes = enrolled_classes.order_by('class_name')

    context = {
        "class_obj": class_obj,
        "assignments": assignments,
        "classes": classes,
        "enrolled_classes": enrolled_classes,
        "notifications": notifications,
        "quizzes": quizzes,
        "unread_count": unread_count,
    }
    return render(request, "students/class_detail.html", context)



@login_required
def notification_redirect(request, notification_id):
    notif = get_object_or_404(StreamNotification, id=notification_id, user=request.user)

    # Mark as read
    if not notif.read:
        notif.read = True
        notif.save()

    # ✅ Attendance session check
    if hasattr(notif, 'attendance_session') and notif.attendance_session:
        return redirect('students:check_in', session_id=notif.attendance_session.id)

    # ✅ If it's a graded assignment
    if notif.assignment and "graded" in notif.message.lower():
        return redirect('students:grades', class_id=notif.assignment.class_obj.id)

    # ✅ If it's a graded quiz
    if notif.quiz and ("graded" in notif.message.lower() or "returned" in notif.message.lower()):
        quiz = get_object_or_404(Quiz, id=notif.quiz_id)
        return redirect(
            reverse("students:quiz_result", kwargs={
                "class_id": quiz.class_obj.id,
                "quiz_id": quiz.id
            })
        )

    # ✅ Otherwise if it's a quiz announcement (not graded)
    if notif.quiz:
        quiz = notif.quiz
        return redirect(
            reverse("students:quiz_confirm", kwargs={
                "class_id": quiz.class_obj.id,
                "quiz_id": quiz.id
            })
        )

    # ✅ Otherwise → assignment detail
    if notif.assignment:
        return redirect('students:assignment_detail', id=notif.assignment.id)

    # Default → class stream
    return redirect('students:class_detail', id=notif.class_obj.id)


@login_required
def archived_classes(request):
    archived_classes = Class.objects.filter(students=request.user, is_archived=True)
    enrolled_classes = request.user.enrolled_classes.filter(is_archived=False)  # 👈 Only active classes
    return render(request, "students/archived_classes.html", {
        "archived_classes": archived_classes,
        "enrolled_classes": enrolled_classes
    })

@login_required
def restore_class(request):
    if request.method == "POST":
        class_id = request.POST.get("class_id")
        try:
            class_obj = Class.objects.get(id=class_id, students=request.user)
            class_obj.is_archived = False
            class_obj.save()
            return redirect("students:archived_classes")
        except Class.DoesNotExist:
            return redirect("students:archived_classes")
@login_required
def archive_class(request):
    if request.method == "POST":
        class_id = request.POST.get("class_id")
        try:
            class_obj = Class.objects.get(id=class_id, students=request.user)
            class_obj.is_archived = True
            class_obj.save()
            return redirect("students:archived_classes")  # ✅ go to archived classes page
        except Class.DoesNotExist:
            return redirect("students:dashboard")
 
@login_required
def unenroll_class(request):
    if request.method == "POST":
        class_id = request.POST.get("class_id")
        try:
            class_obj = Class.objects.get(id=class_id)
            class_obj.students.remove(request.user)
            return redirect("students:dashboard")  # adjust to your dashboard
        except Class.DoesNotExist:
            return redirect("students:dashboard")

from django.shortcuts import render
from teachers.models import Announcement  # import the model from teachers app
from django.contrib.auth.decorators import login_required

@login_required
def student_announcements(request):
    # show all announcements (or filter later if needed)
    announcements = Announcement.objects.all().order_by('-date_posted')
    enrolled_classes = request.user.enrolled_classes.filter(is_archived=False)  # 👈 Only active classes
    
    return render(request, "students/announcements.html", {
        "announcements": announcements,
        "enrolled_classes": enrolled_classes
    })

@login_required
def student_stream(request, class_id):
    class_obj = get_object_or_404(Class, pk=class_id)

    # Make sure the student is enrolled
    if request.user not in class_obj.students.all():
        return HttpResponseForbidden("You are not enrolled in this class.")

    # ✅ Show only notifications that are not scheduled for the future
    notifications = StreamNotification.objects.filter(
    user=request.user,
    class_obj=class_obj,
    scheduled=False  # ✅ exclude scheduled notifications that are not yet active
).filter(
    Q(assignment__isnull=True) |
    Q(assignment__status="assigned") |
    Q(assignment__status="scheduled", assignment__scheduled_for__lte=timezone.now())
).order_by('-created_at')


    unread_count = notifications.filter(read=False).count()

    return render(request, "students/class_detail.html", {
        "notifications": notifications,
        "unread_count": unread_count,
        "class_obj": class_obj,
    })


from django.utils import timezone

@login_required
def assignment_detail(request, id):
    assignment = get_object_or_404(Assignment, id=id)
    submission = Submission.objects.filter(
        assignment=assignment, student=request.user
    ).first()

    now = timezone.now()
    is_past_due = assignment.due_date and now > assignment.due_date

    if request.method == "POST":
        # Hand-in
        if "hand_in" in request.POST and not is_past_due:
            file = request.FILES.get("file")
            if submission:  # update existing
                submission.file = file
                submission.is_submitted = True
                submission.save()
            else:  # create new
                Submission.objects.create(
                    assignment=assignment,
                    student=request.user,
                    file=file,
                    is_submitted=True,
                )

        # Unsubmit
        elif "unsubmit" in request.POST and submission and not is_past_due:
            submission.is_submitted = False
            submission.file = None  # optional: keep file instead of removing
            submission.save()
        # Post Class Comment
        elif "post_class_comment" in request.POST:
            comment_text = request.POST.get("class_comment")
            if comment_text:
                ClassComment.objects.create(
                    assignment=assignment,
                    user=request.user,
                    text=comment_text
                )
        
        # Post Private Comment
        elif "post_private_comment" in request.POST:
            comment_text = request.POST.get("private_comment")
            if comment_text:
                PrivateComment.objects.create(
                    assignment=assignment,
                    user=request.user,
                    text=comment_text
                )

        return redirect("students:assignment_detail", id=assignment.id)

    class_comments = ClassComment.objects.filter(assignment=assignment)
    # Retrieve private comments:
    # If the user is the teacher of the class, show all private comments for this assignment.
    # If the user is a student, show only their private comments for this assignment.
    if request.user == assignment.class_obj.teacher:
        private_comments = PrivateComment.objects.filter(assignment=assignment)
    else: # Assuming the user is a student
        private_comments = PrivateComment.objects.filter(assignment=assignment, user=request.user)

    return render(request, "students/assignment_detail.html", {
        "assignment": assignment,
        "submission": submission,
        "is_past_due": is_past_due,
        "class_comments": class_comments,
        "private_comments": private_comments,
        "is_teacher": request.user == assignment.class_obj.teacher, # Pass this to template
    })

# -------------------------------
# 📩 MESSAGES INBOX
# -------------------------------
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from teachers.models import Class, Message  # adjust if your Message/Class models are in another app

User = get_user_model()  # ✅ ensures your custom user model is used


@login_required
def messages_inbox(request):
    user = request.user
    enrolled_classes = getattr(user, 'enrolled_classes', Class.objects.none()).filter(is_archived=False)

    # Determine contacts based on role
    if user.role == 'teacher':
        # Teachers can message students in their created classes
        contacts = User.objects.filter(
            enrolled_classes__in=user.created_classes.filter(is_archived=False)
        ).distinct().exclude(id=user.id)

    elif user.role == 'student':
        # Students can message teachers AND classmates in their enrolled classes
        teacher_ids = enrolled_classes.values_list('teacher', flat=True)
        classmate_ids = User.objects.filter(
            enrolled_classes__in=enrolled_classes
        ).exclude(id=user.id).values_list('id', flat=True)
        contacts = User.objects.filter(
            Q(id__in=teacher_ids) | Q(id__in=classmate_ids)
        ).distinct()

    elif user.role == 'parent':
        # Parents can message teachers of their child's classes and their own child
        contacts = User.objects.filter(
            Q(role='teacher') | Q(id__in=[child.id for child in user.children.all()])
        ).distinct()

    else:
        contacts = User.objects.none()

    context = {
        'contacts': contacts,
        'other_user': None,  # No conversation selected yet
        'messages': [],
        'enrolled_classes': enrolled_classes
    }
    return render(request, 'students/conversation.html', context)

@login_required
def conversation(request, user_id=None):
    user = request.user
    enrolled_classes = getattr(user, 'enrolled_classes', Class.objects.none()).filter(is_archived=False)

    # Determine contacts based on role
    if user.role == 'teacher':
        contacts = User.objects.filter(
            enrolled_classes__in=user.created_classes.filter(is_archived=False)
        ).distinct().exclude(id=user.id)

    elif user.role == 'student':
        # ✅ Same logic as messages_inbox (include teachers + classmates)
        teacher_ids = enrolled_classes.values_list('teacher', flat=True)
        classmate_ids = User.objects.filter(
            enrolled_classes__in=enrolled_classes
        ).exclude(id=user.id).values_list('id', flat=True)
        contacts = User.objects.filter(
            Q(id__in=teacher_ids) | Q(id__in=classmate_ids)
        ).distinct()

    elif user.role == 'parent':
        contacts = User.objects.filter(
            Q(role='teacher') | Q(id__in=[child.id for child in user.children.all()])
        ).distinct()

    else:
        contacts = User.objects.none()

    # Get conversation messages
    other_user = None
    messages = []
    if user_id:
        other_user = get_object_or_404(User, id=user_id)
        messages = Message.objects.filter(
            Q(sender=user, recipient=other_user) |
            Q(sender=other_user, recipient=user)
        ).order_by('timestamp')

    # Handle sending messages
    if request.method == 'POST' and other_user:
        content = request.POST.get('content')
        if content and content.strip():
            Message.objects.create(sender=user, recipient=other_user, content=content)
            return redirect('students:conversation', user_id=other_user.id)

    context = {
        'contacts': contacts,
        'other_user': other_user,
        'messages': messages,
        'enrolled_classes': enrolled_classes
    }
    return render(request, 'students/conversation.html', context)


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from teachers.models import Assignment, Submission, Class

@login_required
def student_grades(request, class_id=None):
    """
    Show only assignments for a specific class if class_id is provided.
    """
    if class_id:
        # Get the class and verify the student belongs to it
        class_obj = get_object_or_404(Class, id=class_id, students=request.user)
        assignments = Assignment.objects.filter(class_obj=class_obj)
    else:
        # Default: show all assignments for all enrolled classes
        assignments = Assignment.objects.filter(class_obj__students=request.user)

    work_list = []
    for assignment in assignments.select_related("class_obj"):
        submission = Submission.objects.filter(
            assignment=assignment, student=request.user
        ).first()
        work_list.append({
            "assignment": assignment,
            "submission": submission,
        })

    context = {
        "work_list": work_list,
        "class_id": class_id,
    }

    return render(request, "students/grades.html", context)


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from teachers.models import Quiz, Question, Option, StudentAnswer
from .models import StudentQuizAttempt


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # 🔹 Ensure attempt record exists
    attempt, created = StudentQuizAttempt.objects.get_or_create(
        student=request.user,
        quiz=quiz,
        defaults={"status": "in_progress"}  # first time opening
    )

    # 🔹 Check expiration
    if not attempt.is_active():
        if attempt.status == "in_progress":
            attempt.status = "expired"
            attempt.submitted_at = timezone.now()
            attempt.save()
        return render(request, "students/quiz_expired.html", {"quiz": quiz})

    # 🔹 If already submitted before, block re-take
    existing_answers_qs = StudentAnswer.objects.filter(
        student=request.user,
        question__quiz=quiz
    ).select_related("selected_option", "question")
    submitted = attempt.status in ["completed", "expired"]

    if request.method == "POST":
        if submitted:
            messages.info(request, "You already submitted this quiz.")
            return redirect("students:class_detail", id=quiz.class_obj.id)

        # ✅ Save answers
        for question in quiz.questions.all():
            field_name = f"question_{question.id}"
            value = request.POST.get(field_name)
            if not value:
                continue

            # Multiple-choice
            if question.question_type == "multiple-choice":
                try:
                    opt = Option.objects.get(id=value, question=question)
                except Option.DoesNotExist:
                    continue
                StudentAnswer.objects.update_or_create(
                    student=request.user,
                    quiz=quiz,  # ✅ new field
                    question=question,
                    defaults={
                        "selected_option": opt,
                        "text_answer": None,
                        "score": 1 if opt.is_correct else 0,
                    }
                )

            # Identification
            elif question.question_type == "identification":
                text = value.strip()
                correct_opt = question.options.filter(is_correct=True).first()
                score = 1 if correct_opt and correct_opt.text.strip().lower() == text.lower() else 0
                StudentAnswer.objects.update_or_create(
                    student=request.user,
                    quiz=quiz,  # ✅ new field
                    question=question,
                    defaults={
                        "text_answer": text,
                        "selected_option": None,
                        "score": score,
                    }
                )

            # Essay
            else:
                text = value.strip()
                StudentAnswer.objects.update_or_create(
                    student=request.user,
                    quiz=quiz,  # ✅ new field
                    question=question,
                    defaults={
                        "text_answer": text,
                        "selected_option": None,
                        "score": 0,  # Teacher will grade later
                    }
                )

        # ✅ Mark quiz attempt as completed
        attempt.status = "completed"
        attempt.submitted_at = timezone.now()
        attempt.save()

        messages.success(request, "Quiz submitted — marked as Turned in.")
        return redirect("students:class_detail", id=quiz.class_obj.id)

    # Prepare Q&A pairs for rendering
    answers_by_qid = {a.question_id: a for a in existing_answers_qs}
    qa_pairs = [{"question": q, "answer": answers_by_qid.get(q.id)} for q in quiz.questions.all()]

    return render(request, "students/take_quiz.html", {
        "quiz": quiz,
        "submitted": submitted,
        "qa_pairs": qa_pairs,
        "time_remaining": attempt.time_remaining(),  # ⏰ countdown for template
    })

@login_required
def quiz_history(request, class_id, quiz_id):
    class_obj = get_object_or_404(Class, id=class_id, students=request.user)
    quiz = get_object_or_404(Quiz, id=quiz_id, class_obj=class_obj)
    attempt = get_object_or_404(StudentQuizAttempt, student=request.user, quiz=quiz)

    # Fetch all answers for this quiz attempt
    answers = StudentAnswer.objects.filter(
        student=request.user,
        question__quiz=quiz
    ).select_related("question", "selected_option")

    # Organize answers by question ID for easy lookup
    answers_by_qid = {a.question_id: a for a in answers}

    # Prepare Q&A pairs for rendering
    qa_pairs = [{"question": q, "answer": answers_by_qid.get(q.id)} for q in quiz.questions.all()]

    return render(request, "students/quiz_history.html", {
        "class_obj": class_obj,
        "quiz": quiz,
        "attempt": attempt,
        "qa_pairs": qa_pairs,
    })

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from teachers.models import Quiz
from .models import StudentQuizAttempt

@login_required
def quiz_confirm(request, class_id, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, class_obj_id=class_id)

    # Prevent duplicate attempts
    if StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).exists():
        return redirect("students:take_quiz", quiz_id=quiz.id)

    if request.method == "POST":
        # Redirect to take_quiz (this is where timer will start)
        return redirect("students:take_quiz",  quiz_id=quiz.id)

    return render(request, "students/quiz_confirm.html", {"quiz": quiz})

@login_required
def quiz_result(request, class_id, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, class_obj__id=class_id)
    student = request.user

    # Get all answers of this student for this quiz
    answers = StudentAnswer.objects.filter(student=student, quiz=quiz).select_related("question")

    # Compute total score (if any are graded)
    total_score = sum(a.score for a in answers if a.score is not None)
    max_score = quiz.questions.count()  # or sum of max per question if different weights

    return render(request, "students/quiz_result.html", {
        "quiz": quiz,
        "total_score": total_score if answers.exists() else None,
        "max_score": max_score,
    })

# students/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from teachers.models import AttendanceSession, AttendanceRecord
from geopy.distance import geodesic
from django.utils import timezone

@login_required
def check_in(request, session_id):
    session = get_object_or_404(AttendanceSession, pk=session_id)
    record = get_object_or_404(AttendanceRecord, session=session, student=request.user)

    # Already checked in
    if record.status == "present":
        messages.info(request, "You have already checked in for this session.")
        return redirect('students:class_detail', id=session.class_obj.id)

    # Time limit check
    if session.end_time and timezone.now() > session.end_time:
        messages.error(request, "This attendance session has ended.")
        return redirect('students:class_detail', id=session.class_obj.id)

    if request.method == "POST":
        lat = float(request.POST.get("latitude", 0.0))
        lng = float(request.POST.get("longitude", 0.0))

        # Calculate distance
        distance = geodesic((lat, lng), (session.latitude, session.longitude)).meters

        record.latitude = lat
        record.longitude = lng
        record.distance_from_class = distance

        if distance <= session.radius_m:
            record.status = "present"
            record.check_in_time = timezone.now()
            record.save()
            messages.success(request, "Checked in successfully!")
        else:
            messages.error(request, f"You are too far from the class to check in. ({int(distance)}m away)")
        
        return redirect('students:class_detail', id=session.class_obj.id)

    return render(request, "students/check_in.html", {
        "session": session,
        "record": record
    })
