from django.shortcuts import render, redirect
from django.shortcuts import render
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import AssignmentAttachment, AssignmentLink, Class, ClassComment, PrivateComment
from django.shortcuts import render, redirect, get_object_or_404
from .models import Class, Assignment, Event, Submission, AssignmentVideo
from .forms import AssignmentForm, SubmissionForm, EventForm
import csv
import io
import qrcode
import base64
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .models import Class
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.views.decorators.cache import never_cache
User = get_user_model()
@login_required
@never_cache
def teacherdashboard(request):
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    return render(request, 'teachers/dashboard.html', {
        'classes': classes,
        'class_count': classes.count()
    })
@login_required
def message(request):
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    
    return render(request, "teachers/messages.html",{
        'classes': classes,
        'class_count': classes.count()
        })

@login_required
def calendar(request):
    events = Event.objects.all().order_by("date")  # all events (teachers, students, parents see same list)
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            return redirect("teachers:calendar")
    else:
        form = EventForm()

    return render(request, "teachers/calendar.html", {
        "events": events,
        "form": form,
        'classes': classes,
        'class_count': classes.count()
    })

@login_required
def announcement(request):
    return render(request, 'teachers/announcement.html')


from django.db.models import Avg
from django.db.models import Count, Q, F, ExpressionWrapper, IntegerField

from django.db.models import Count, Q, F, IntegerField, ExpressionWrapper

@login_required
def subject(request, id):
    class_obj = get_object_or_404(Class, pk=id)
    tab = request.GET.get('tab', 'marks')  # default tab
    notifications = StreamNotification.objects.filter(
        user=request.user,
        class_obj=class_obj
    ).order_by('-created_at')

    unread_count = StreamNotification.objects.filter(
        class_obj=class_obj,
        user=request.user,
        read=False
    ).count()

    is_teacher = class_obj.teacher == request.user
    classes = Class.objects.filter(teacher=request.user, is_archived=False)

    # === Quizzes with Turned in / Missing / Assigned ===
    quizzes = (
        Quiz.objects.filter(class_obj=class_obj)
        .annotate(
            turned_in=Count("attempts", filter=Q(attempts__status="completed"), distinct=True),
            assigned=Count("class_obj__students", distinct=True),
        )
        .annotate(
            missing=ExpressionWrapper(
                F("assigned") - F("turned_in"),
                output_field=IntegerField()
            )
        )
        .order_by("-created_at")
    )

    # === Assignments with Turned in / Missing / Assigned ===
    assignments = (
        Assignment.objects.filter(class_obj=class_obj)
        .annotate(
            turned_in=Count("submissions", filter=Q(submissions__file__isnull=False), distinct=True),
            assigned=Count("class_obj__students", distinct=True),
        )
        .annotate(
            missing=ExpressionWrapper(
                F("assigned") - F("turned_in"),
                output_field=IntegerField()
            )
        )
        .order_by("-created_at")
    )

    gradebook = []
    assignment_averages = {}

    if is_teacher:
        students = class_obj.students.all()
        for student in students:
            row = {"student": student, "grades": [], "average": None}
            total = 0
            count = 0

            for assignment in assignments:
                submission = Submission.objects.filter(student=student, assignment=assignment).first()
                grade = submission.grade if submission else None
                published = submission.is_published if submission else False

                row["grades"].append({
                    "assignment": assignment,
                    "grade": grade,
                    "is_published": published,
                    "submission": submission
                })

                if grade is not None:
                    total += grade
                    count += 1
                    assignment_averages.setdefault(assignment.id, []).append(grade)

            row["average"] = round(total / count, 2) if count > 0 else None
            gradebook.append(row)

        # Assignment averages
        for assignment in assignments:
            avg = Submission.objects.filter(assignment=assignment, grade__isnull=False).aggregate(Avg("grade"))["grade__avg"]
            assignment_averages[assignment.id] = round(avg, 2) if avg else None

             # Handle Announcements (Teacher posts)
    if request.method == "POST":
        # Teacher posts an announcement
        announcement_text = request.POST.get("announcement_text")

        if announcement_text:
            # Create a notification for each student in the class
            students = class_obj.students.all()
            for student in students:
                StreamNotification.objects.create(
                    user=student,
                    class_obj=class_obj,
                    message=f"📢 {request.user.get_full_name()} announced: {announcement_text}"
                )

            # Also record a copy for the teacher’s own stream (so they can see it too)
            StreamNotification.objects.create(
                user=request.user,
                class_obj=class_obj,
                message=f"You announced: {announcement_text}"
            )

            messages.success(request, "Announcement posted successfully!")
            return redirect("teachers:subject", id=class_obj.pk)

    if request.method == "POST":
        if request.FILES.get("banner"):
            class_obj.banner = request.FILES["banner"]
            class_obj.banner_color = None
        elif request.POST.get("banner_color"):
            class_obj.banner_color = request.POST["banner_color"]
            class_obj.banner = None
            class_obj.save()


        return redirect("teachers:subject", id=class_obj.pk)

    return render(request, 'teachers/subject.html', {
        'class_obj': class_obj,
        'assignments': assignments,
        'classes': classes,
        'class_count': classes.count(),
        'gradebook': gradebook if is_teacher else None,
        'assignment_averages': assignment_averages if is_teacher else None,
        'is_teacher': is_teacher,
        "unread_count": unread_count,
        "notifications": notifications,
        "quizzes": quizzes,
        'active_tab': tab,
    })

from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
@require_POST
def update_grade(request, class_id, submission_id):
    class_obj = get_object_or_404(Class, pk=class_id, teacher=request.user)
    submission = get_object_or_404(Submission, pk=submission_id, assignment__class_obj=class_obj)

    try:
        grade_val = request.POST.get("grade")
        grade = float(grade_val) if grade_val != "" else None
    except ValueError:
        return JsonResponse({"error": "Invalid grade"}, status=400)

    submission.grade = grade
    submission.save()

    # Recompute averages
    student_avg = Submission.objects.filter(
        student=submission.student, assignment__class_obj=class_obj, grade__isnull=False
    ).aggregate(Avg("grade"))["grade__avg"]

    assignment_avg = Submission.objects.filter(
        assignment=submission.assignment, grade__isnull=False
    ).aggregate(Avg("grade"))["grade__avg"]

    return JsonResponse({
        "success": True,
        "grade": submission.grade,
        "student_id": submission.student.id,
        "assignment_id": submission.assignment.id,
        "student_avg": round(student_avg, 2) if student_avg else None,
        "assignment_avg": round(assignment_avg, 2) if assignment_avg else None,
    })


from django.utils import timezone
from datetime import datetime

@login_required
def assignment_form(request, id):
    class_obj = get_object_or_404(Class, id=id)
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.class_obj = class_obj

            # ✅ Check if teacher scheduled it
            schedule_date = request.POST.get("schedule_date")
            schedule_time = request.POST.get("schedule_time")

            if schedule_date and schedule_time:
                scheduled_datetime = datetime.strptime(f"{schedule_date} {schedule_time}", "%Y-%m-%d %H:%M")
                assignment.scheduled_for = timezone.make_aware(scheduled_datetime)
                assignment.status = "scheduled"
                assignment.save()
                form.save_m2m()

    # ✅ Optional: create a hidden notification for the teacher only (not students yet)
                StreamNotification.objects.create(
                user=request.user,
                class_obj=class_obj,
                assignment=assignment,
                message=f"Scheduled assignment '{assignment.title}' for {assignment.scheduled_for.strftime('%b %d, %Y %I:%M %p')}",
                scheduled=True,
                scheduled_for=assignment.scheduled_for
            )

            else:
                assignment.status = "assigned"

            assignment.save()
            form.save_m2m()

            # ✅ Handle uploaded files
            for f in request.FILES.getlist('attachment'):
                AssignmentAttachment.objects.create(assignment=assignment, file=f)

            # ✅ Handle attached links
            attached_links_json = request.POST.get("attached_links", "[]")
            try:
                attached_links = json.loads(attached_links_json)
            except json.JSONDecodeError:
                attached_links = []

            for link in attached_links:
                if link.strip():
                    AssignmentLink.objects.create(assignment=assignment, url=link.strip())

            # ✅ Save YouTube videos
            for url in request.POST.getlist("youtube_urls"):
                if url.strip():
                    AssignmentVideo.objects.create(assignment=assignment, url=url.strip())

            # ✅ If assigned now → send notifications immediately
            if assignment.status == "assigned":
                StreamNotification.objects.create(
                    user=request.user,
                    class_obj=class_obj,
                    assignment=assignment,
                    message=f"{request.user.get_full_name()} posted a new assignment: {assignment.title}",
                )

                for student in class_obj.students.all():
                    StreamNotification.objects.create(
                        user=student,
                        class_obj=class_obj,
                        assignment=assignment,
                        message=f"New assignment '{assignment.title}' has been posted by {request.user.get_full_name()}!",
                    )

                messages.success(request, "Assignment created and notifications sent!")

            # ✅ If scheduled → store notifications as hidden
            else:
                 messages.info(
                    request,
                        f"Assignment scheduled for {assignment.scheduled_for.strftime('%b %d, %Y %I:%M %p')}."
            )
        return redirect("teachers:subject", id=class_obj.id)
    
    else:
        form = AssignmentForm()

    return render(request, "teachers/assignment_form.html", {
        "form": form,
        "class_obj": class_obj,
        "classes": classes,
        "students": class_obj.students.all(),
    })

@login_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Optional: check if the logged-in user is the teacher of this class
    if assignment.class_obj.teacher != request.user:
        messages.error(request, "You are not allowed to delete this assignment.")
        return redirect("teachers:subject", id=assignment.class_obj.id)

    assignment.delete()
    messages.success(request, "Assignment deleted successfully.")
    return redirect("teachers:subject", id=assignment.class_obj.id)

@login_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = request.user  # because students are also AUTH_USER_MODEL
            submission.save()
            return redirect("class_detail", id=assignment.class_obj.id)
    else:
        form = SubmissionForm()
    return render(request, "students/submit_assignment.html", {"form": form, "assignment": assignment})

from django.utils import timezone

@login_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Check if logged in user is the teacher of the class
    is_teacher = assignment.class_obj.teacher == request.user  

     # check due date
    is_past_due = False
    if assignment.due_date and timezone.now() > assignment.due_date:
        is_past_due = True
        
     # --- Handle POST actions ---
    if request.method == "POST":
        action = request.POST.get("action")
        submission_id = request.POST.get("submission_id")
        student_id = request.POST.get("student_id")  # used for not_turned_in students

        # Return with grade
        if action == "return" and submission_id:
            sub = get_object_or_404(Submission, id=submission_id, assignment=assignment)
            grade = request.POST.get("grade")
            feedback = request.POST.get("feedback", "")
            try:
                sub.grade = int(grade)
                sub.feedback = feedback
                sub.returned = True
                sub.save()
                messages.success(request, f"Returned work to {sub.student.get_full_name()} with grade {grade}.")
            except ValueError:
                messages.error(request, "Invalid grade entered.")
            return redirect("teachers:assignment_detail", assignment_id=assignment.id)
        
        # Post Private Comment (Teacher to Student)
        elif "post_private_comment" in request.POST and is_teacher:
            comment_text = request.POST.get("private_comment")
            target_student_id = request.POST.get("target_student_id") # Assuming a hidden input for student ID
            if comment_text and target_student_id:
                target_student = get_object_or_404(User, id=target_student_id)
                PrivateComment.objects.create(
                    assignment=assignment,
                    user=request.user, # Teacher is the commenter
                    recipient=target_student, # Student is the recipient
                    text=comment_text,
                )
                messages.success(request, f"Private comment sent to {target_student.get_full_name()}.")
            return redirect("teachers:assignment_detail", assignment_id=assignment.id)


    # Student-side: get their own submission
    student_submission = None
    if not is_teacher:
        student_submission = Submission.objects.filter(
            assignment=assignment, student=request.user
        ).first()

    # Teacher-side: get all enrolled students & submissions
    submissions = []
    not_turned_in = []
    turned_in_count = 0
    assigned_count = 0

    if is_teacher:
        # All enrolled students
        enrolled_students = assignment.class_obj.students.all()

        # All submissions
        submissions = Submission.objects.filter(assignment=assignment).select_related("student")
        print(f"DEBUG (Teacher View): Submissions for assignment {assignment.id}: {submissions}")

        # Students who submitted
        submitted_students = submissions.values_list("student_id", flat=True)
        print(f"DEBUG (Teacher View): Submitted student IDs: {submitted_students}")

        # Students who did NOT submit
        not_turned_in = enrolled_students.exclude(id__in=submitted_students)
        print(f"DEBUG (Teacher View): Not turned in students: {not_turned_in}")

        # Stats
        turned_in_count = submissions.count()
        assigned_count = enrolled_students.count() - turned_in_count
        
        # For teachers, get all private comments for this assignment
        # Filter by comments where the assignment matches, and either the teacher is the user or the recipient
        private_comments = PrivateComment.objects.filter(
            assignment=assignment
        ).filter(
            Q(user__role='student', recipient=request.user) | # Student to this teacher
            Q(user=request.user, recipient__role='student') # This teacher to student
        ).order_by('created_at')
        print(f"DEBUG (Teacher View): Private comments for teacher view: {private_comments}")
    else:
        # For students, get only their private comments for this assignment
        # Filter by comments sent by the student, or by the teacher to this student
        private_comments = PrivateComment.objects.filter(
            Q(assignment=assignment, user=request.user) | # Comments by this student
            Q(assignment=assignment, recipient=request.user) # Comments to this student
        ).order_by('created_at')
        print(f"DEBUG (Student View): Private comments for student view: {private_comments}")


    context = {
        "assignment": assignment,
        "is_teacher": is_teacher,
        "student_submission": student_submission,
        "submissions": submissions,
        "not_turned_in": not_turned_in,
        "turned_in_count": turned_in_count,
        "assigned_count": assigned_count,
        "is_past_due": is_past_due,
        "private_comments": private_comments, # Pass private comments to context
    }
    return render(request, "teachers/assignment_detail.html", context)

@login_required
@require_POST
def post_class_comment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    comment_text = request.POST.get("comment")

    if comment_text:
        ClassComment.objects.create(
            assignment=assignment,
            user=request.user,
            text=comment_text
        )
        messages.success(request, "Class comment posted successfully!")
    else:
        messages.error(request, "Comment cannot be empty.")
    return redirect("teachers:assignment_detail", assignment_id=assignment.id)

    # ✅ Handle scoring submission (integer only)
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        question_id = request.POST.get("question_id")
        score = request.POST.get("score")

        if student_id and question_id:
            key = f"{student_id}_{question_id}"
            answer = answers.get(key)
            if answer:
                answer.score = int(score or 0)
                answer.save()

                # ✅ Create a StreamNotification for that student
                StreamNotification.objects.create(
                    user=answer.student,
                    class_obj=class_obj,
                    quiz=quiz,
                    message=f"Your quiz '{quiz.title}' has been graded by {request.user.get_full_name()}."
                )

                messages.success(request, "Score saved and student notified!")

        return redirect("teachers:quiz_detail", class_id=class_obj.id, quiz_id=quiz.id)


    return render(request, "teachers/quiz_detail.html", {
        "class_obj": class_obj,
        "quiz": quiz,
        "turned_in_attempts": turned_in_attempts,
        "missing_students": missing_students,
        "answers": answers,
        "total_scores": total_scores,
    })

from .google_utils import create_drive_folder

@csrf_exempt
@login_required
def create_class(request):
    print("🧩 create_class view triggered")
    if request.method == "POST":
        class_name = request.POST.get("class_name")
        subject_name = request.POST.get("subject_name")
        section = request.POST.get("section")
        time = request.POST.get("time")
        banner_color = request.POST.get("banner_color", "#ffffff")

        # ✅ Create main folder
        main_folder = create_drive_folder(f"{class_name} - {section}")
        drive_folder_link = main_folder.get("webViewLink", "")


        # ✅ Create subfolders for structure
        subfolders = {}
        for name in ["Materials", "Assignments", "Submissions", "Quizzes"]:
            subfolders[name] = create_drive_folder(name, parent_id=main_folder["id"])

        # ✅ Save class
        new_class = Class.objects.create(
            class_name=class_name,
            subject_name=subject_name,
            section=section,
            time=time,
            banner_color=banner_color,
            drive_folder_link=drive_folder_link,
            teacher=request.user,
        )

        messages.success(
            request,
            f"Class '{new_class.class_name}' created successfully! Code: {new_class.code}"
        )
        return redirect("teachers:dashboard")
    
@login_required 
def archive_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    if request.method == "POST":
        class_obj.is_archived = True
        class_obj.save()
        return redirect("teachers:archived_classes")
    return redirect("teachers:dashboard")

@login_required
def restore_archived_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    if request.method == "POST":
        class_obj.is_archived = False
        class_obj.save()
    return redirect("teachers:archived_classes")

@login_required
def archived_classes(request):
    archived = Class.objects.filter(teacher=request.user, is_archived=True)
    classes = Class.objects.filter(teacher=request.user)
    return render(request, "teachers/archive_classes.html", {"classes": archived, 'all_classes': classes, 'class_count': classes.count()})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import AnnouncementForm
from .models import Announcement

@login_required
def announcement_list(request):
    announcements = Announcement.objects.all().order_by('-date_posted')
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    # filters
    search_query = request.GET.get("search")
    category = request.GET.get("category")
    priority = request.GET.get("priority")
    sort = request.GET.get("sort")

    if search_query:
        announcements = announcements.filter(title__icontains=search_query) | announcements.filter(content__icontains=search_query)
    if category:
        announcements = announcements.filter(category=category)
    if priority:
        announcements = announcements.filter(priority=priority)
    if sort == "oldest":
        announcements = announcements.order_by("date_posted")

    # only teachers can add announcements
    form = None
    if hasattr(request.user, "role") and request.user.role in ["teacher", "school_admin"]:
        if request.method == "POST":
            form = AnnouncementForm(request.POST)
            if form.is_valid():
                ann = form.save(commit=False)
                ann.author = request.user
                ann.save()
                return redirect("teachers:announcement_list")
        else:
            form = AnnouncementForm()

    return render(request, "teachers/announcement.html", {
        "announcements": announcements,
        "form": form,
        'classes': classes,
        'class_count': classes.count()
    })


@login_required
def announcement_detail(request, id):
    ann = get_object_or_404(Announcement, id=id)
    return render(request, "teachers/announcement_detail.html", {"announcement": ann})
from django.http import HttpResponseForbidden

@login_required
def announcement_edit(request, id):
    ann = get_object_or_404(Announcement, id=id)

    # only the author (teacher) or an admin can edit
    if not hasattr(request.user, "role") or (request.user != ann.author and request.user.role != "school_admin"):
        return HttpResponseForbidden("You are not allowed to edit this announcement.")

    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=ann)
        if form.is_valid():
            form.save()
            return redirect("teachers:announcement_list")
    else:
        form = AnnouncementForm(instance=ann)

    return render(request, "teachers/announcement_form.html", {"form": form, "announcement": ann})


@login_required
def announcement_delete(request, id):
    ann = get_object_or_404(Announcement, id=id)

    # only the author (teacher) or an admin can delete
    if not hasattr(request.user, "role") or (request.user != ann.author and request.user.role != "school_admin"):
        return HttpResponseForbidden("You are not allowed to delete this announcement.")

    if request.method == "POST":
        ann.delete()
        return redirect("teachers:announcement_list")

    return render(request, "teachers/announcement_confirm_delete.html", {"announcement": ann})

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Class  # change to your actual model name

def edit_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == "POST":
        class_obj.class_name = request.POST.get("class_name")
        class_obj.subject_name = request.POST.get("subject_name")
        class_obj.section = request.POST.get("section")
        class_obj.time = request.POST.get("time")
        class_obj.save()
        messages.success(request, "Class updated successfully!")
        return redirect("teachers:dashboard")  # change to your page


@login_required
def class_grades(request, class_id):
    # Ensure only class teacher may access
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    students = class_obj.students.all().order_by('last_name', 'first_name')
    assignments = class_obj.assignments.all().order_by('created_at')

    # Build gradebook: ensure there's a Submission object for each student/assignment
    gradebook = []
    assignment_averages = {a.id: {"total": 0.0, "count": 0} for a in assignments}

    # Handle form POST (update grades/publish flags / bulk action)
    if request.method == "POST":
        # Bulk action: set all missing to 0
        if "bulk_zero" in request.POST:
            # set grade = 0 for all submissions that are missing (no file and no grade)
            for assignment in assignments:
                missing_subs = Submission.objects.filter(
                    assignment=assignment, file__isnull=True, grade__isnull=True
                )
                for s in missing_subs:
                    s.grade = 0
                    s.is_published = False  # default: keep unpublished until teacher publishes
                    s.save()
            messages.success(request, "All missing submissions set to 0 (draft).")
            return redirect("teachers:class_grades", class_id=class_id)

        # Save edits (grades + publish checkboxes) across the whole table
        # Form fields are: grade_<submission_id>, publish_<submission_id>
        for key, value in request.POST.items():
            if key.startswith("grade_"):
                try:
                    sub_id = int(key.split("_", 1)[1])
                    sub = Submission.objects.filter(id=sub_id).first()
                    if not sub:
                        continue
                    # parse grade (allow blank to clear)
                    grade_val = value.strip()
                    if grade_val == "":
                        sub.grade = None
                    else:
                        try:
                            sub.grade = float(grade_val)
                        except ValueError:
                            # invalid grade - skip or set message
                            continue
                    sub.save()
                except Exception:
                    continue

        # Now handle publish checkboxes
        # For each submission, if publish_<id> in POST --> True, else False
        all_submission_ids = Submission.objects.filter(assignment__class_obj=class_obj).values_list('id', flat=True)
        for sid in all_submission_ids:
            publish_key = f"publish_{sid}"
            sub = Submission.objects.filter(id=sid).first()
            if not sub:
                continue
            sub.is_published = (publish_key in request.POST)
            sub.save()

        messages.success(request, "Grades updated.")
        return redirect("teachers:class_grades", class_id=class_id)

    # GET: Build the gradebook structure for template
    for student in students:
        row = {"student": student, "grades": [], "average": None}
        total = 0.0
        count = 0
        for assignment in assignments:
            sub, created = Submission.objects.get_or_create(assignment=assignment, student=student)
            g = sub.grade
            row["grades"].append({"submission": sub, "grade": g})
            if g is not None:
                total += float(g)
                count += 1
                assignment_averages[assignment.id]["total"] += float(g)
                assignment_averages[assignment.id]["count"] += 1
        row["average"] = round(total / count, 2) if count > 0 else None
        gradebook.append(row)

    # finalize assignment averages
    for a_id, d in assignment_averages.items():
        if d["count"] > 0:
            d["average"] = round(d["total"] / d["count"], 2)
        else:
            d["average"] = None

    context = {
        "class_obj": class_obj,
        "assignments": assignments,
        "gradebook": gradebook,
        "assignment_averages": assignment_averages,
    }
    return render(request, "teachers/class_grades.html", context)


@login_required
def export_grades(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    assignments = class_obj.assignments.all().order_by('created_at')
    students = class_obj.students.all().order_by('last_name', 'first_name')

    # Prepare CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{class_obj.class_name}_grades.csv"'
    writer = csv.writer(response)

    header = ["Student Email", "Student Name"] + [a.title for a in assignments]
    writer.writerow(header)

    for student in students:
        row = [student.email, student.get_full_name()]
        for a in assignments:
            sub = Submission.objects.filter(assignment=a, student=student).first()
            row.append(sub.grade if sub and sub.grade is not None else "")
        writer.writerow(row)

    return response


@login_required
def import_grades(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    assignments = {a.title: a for a in class_obj.assignments.all()}

    if request.method == "POST" and request.FILES.get("file"):
        csv_file = request.FILES["file"]
        try:
            decoded = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
        except Exception as e:
            messages.error(request, "Could not read CSV file.")
            return redirect("teachers:class_grades", class_id=class_id)

        updated = 0
        skipped = 0
        for row in reader:
            # Expecting first columns to be "Student Email" and/or "Student Name"
            email = row.get("Student Email") or row.get("student_email") or row.get("Email")
            name = row.get("Student Name") or row.get("student_name") or row.get("Name")

            student = None
            if email:
                student = User.objects.filter(email=email.strip()).first()
            if not student and name:
                # fallback search by full name
                parts = name.strip().split()
                if len(parts) >= 2:
                    # try by first and last
                    student = User.objects.filter(first_name__iexact=parts[0], last_name__iexact=parts[-1]).first()
                else:
                    student = User.objects.filter(first_name__iexact=name.strip()).first()

            if not student:
                skipped += 1
                continue

            # For each assignment column in row, update grade
            for col, val in row.items():
                if col in ("Student Email", "student_email", "Email", "Student Name", "student_name", "Name"):
                    continue
                # match assignment by title exactly
                assignment = assignments.get(col)
                if not assignment:
                    continue
                # parse grade
                if val is None or val == "":
                    continue
                try:
                    grade_val = float(val)
                except ValueError:
                    continue
                sub, _ = Submission.objects.get_or_create(assignment=assignment, student=student)
                sub.grade = grade_val
                # imported grades are saved as drafts (not published) by default
                sub.is_published = False
                sub.save()
                updated += 1

        messages.success(request, f"Imported grades: {updated} values; skipped {skipped} students/rows.")
        return redirect("teachers:class_grades", class_id=class_id)

    messages.error(request, "No file uploaded.")
    return redirect("teachers:class_grades", class_id=class_id)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Message, Class  # assuming Message model exists
from django.http import JsonResponse
from django.template.loader import render_to_string

User = get_user_model()


from itertools import chain
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required

@login_required
def messages_inbox(request):
    user = request.user
    query = request.GET.get('q', '')

    # === 1. Get classes user is involved in ===
    if user.role == 'teacher':
        classes = Class.objects.filter(teacher=user, is_archived=False)
    elif user.role == 'student':
        classes = Class.objects.filter(students=user, is_archived=False)
    elif user.role == 'parent':
        parent_profile = getattr(user, 'parent_profile', None)
        if parent_profile:
            classes = Class.objects.filter(students__in=parent_profile.students.all(), is_archived=False).distinct()
        else:
            classes = Class.objects.none()
    else:
        classes = Class.objects.none()

    # === 2. Determine contacts based on role ===
    contacts = User.objects.none()

    if user.role == 'teacher':
        # Get enrolled students
        students = User.objects.filter(enrolled_classes__in=classes, role='student').distinct()

        # Get parents of those students
        parents = User.objects.filter(
            parent_profile__students__in=students,
            role='parent'
        ).distinct()

        contacts = list(chain(students, parents))

    elif user.role == 'student':
        # Get teachers of student's classes
        teachers = User.objects.filter(created_classes__in=classes, role='teacher').distinct()

        # Get student's parents
        parents = User.objects.filter(
            parent_profile__students=user,
            role='parent'
        ).distinct()

        contacts = list(chain(teachers, parents))

    elif user.role == 'parent':
        parent_profile = getattr(user, 'parent_profile', None)
        if parent_profile:
            # Get linked students
            students = parent_profile.students.filter(role='student')

            # Get teachers of those students' classes
            teachers = User.objects.filter(
                created_classes__students__in=students,
                role='teacher'
            ).distinct()

            contacts = list(chain(students, teachers))
        else:
            contacts = []

    # Remove duplicates & current user
    contact_ids = {c.id for c in contacts if c.id != user.id}
    contacts = User.objects.filter(id__in=contact_ids)

    # === 3. Apply search filter ===
    if query:
        contacts = contacts.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )

    # === 4. Group contacts by role ===
    contacts_teachers = contacts.filter(role='teacher')
    contacts_students = contacts.filter(role='student')
    contacts_parents = contacts.filter(role='parent')

    # === 5. Handle AJAX contact list updates ===
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = ""
        for contact in contacts:
            html += render_to_string('teachers/contact_item.html', {'contact': contact}, request=request)
        if not contacts.exists():
            html = '<p class="text-muted p-3">No contacts found.</p>'
        return JsonResponse({'html': html})

    # === 6. Render template ===
    context = {
        'classes': classes,
        'class_count': classes.count(),
        'contacts_teachers': contacts_teachers,
        'contacts_students': contacts_students,
        'contacts_parents': contacts_parents,
        'other_user': None,
        'messages': [],
        'query': query,
    }
    return render(request, 'teachers/conversation.html', context)


@login_required
def conversation(request, user_id):
    classes = Class.objects.filter(teacher=request.user, is_archived=False)
    user = request.user
    other_user = get_object_or_404(User, id=user_id)

    messages = Message.objects.filter(
        Q(sender=user, recipient=other_user) |
        Q(sender=other_user, recipient=user)
    ).order_by('timestamp')

    # Determine contacts for sidebar based on role
    if user.role == 'teacher':
        contacts = User.objects.filter(role__in=['student', 'parent']).exclude(id=user.id)
    elif user.role == 'student':
        contacts = User.objects.filter(role__in=['teacher', 'parent']).exclude(id=user.id)
    elif user.role == 'parent':
        contacts = User.objects.filter(role__in=['teacher', 'student']).exclude(id=user.id)
    else:
        contacts = User.objects.none()

    # Group contacts by role
    contacts_teachers = contacts.filter(role='teacher')
    contacts_students = contacts.filter(role='student')
    contacts_parents = contacts.filter(role='parent')

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(sender=user, recipient=other_user, content=content)
            return redirect('teachers:conversation', user_id=other_user.id)

    context = {
        'classes': classes,
        'class_count': classes.count(),
        'contacts_teachers': contacts_teachers,
        'contacts_students': contacts_students,
        'contacts_parents': contacts_parents,
        'other_user': other_user,
        'messages': messages,
    }
    return render(request, 'teachers/conversation.html', context)


from .models import StreamNotification

@login_required
def notification_redirect(request, notification_id):
    notif = get_object_or_404(StreamNotification, id=notification_id)

    # Mark as read
    if not notif.read:
        notif.read = True
        notif.save()
    
    # Attendance session
    if hasattr(notif, 'attendance_session') and notif.attendance_session:
        return redirect('teachers:attendance_session_detail', session_id=notif.attendance_session.id)

    # Assignment
    if notif.assignment:
        return redirect('teachers:assignment_detail', assignment_id=notif.assignment_id)

    # Quiz
    if notif.quiz:
        quiz = get_object_or_404(Quiz, id=notif.quiz_id)
        return redirect(
            reverse("teachers:quiz_detail", kwargs={
                "class_id": quiz.class_obj.id,
                "quiz_id": quiz.id
            })
        )

    # Default → subject
    return redirect('teachers:subject', class_id=notif.class_obj.id)

from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect

@login_required
def clear_notifications(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
    class_obj.notifications.all().delete()  # ✅ Delete all linked to this class
    messages.success(request, "All notifications have been cleared.")
    return redirect(reverse('teachers:subject', args=[class_id]))

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["DELETE"])
def delete_notification(request, id):
    try:
        notif = StreamNotification.objects.get(id=id, user=request.user)
        notif.delete()
        return JsonResponse({'success': True})
    except StreamNotification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def bulk_return_submissions(request):
    import json
    data = json.loads(request.body.decode("utf-8"))
    student_ids = data.get("student_ids", [])
    assignment_id = data.get("assignment_id")

    submissions = Submission.objects.filter(
        assignment_id=assignment_id,
        student_id__in=student_ids
    ).select_related("student", "assignment", "assignment__class_obj")

    updated = []
    notifications = []

    for sub in submissions:
        sub.is_returned = True
        sub.save()

        # Only notify if a grade exists
        if sub.grade is not None:
            # Prepare notification
            message = f"{request.user.get_full_name()} returned your assignment '{sub.assignment.title}' with grade: {sub.grade}/{sub.assignment.points}."
            
            notif = StreamNotification(
                user=sub.student,
                assignment=sub.assignment,
                class_obj=sub.assignment.class_obj,
                message=message
            )
            notifications.append(notif)

        updated.append({
            "id": sub.id,
            "student_id": sub.student.id,
            "student_name": sub.student.get_full_name(),
            "grade": sub.grade,
        })

    # Create all notifications at once (bulk_create is more efficient)
    if notifications:
        StreamNotification.objects.bulk_create(notifications)

    return JsonResponse({"success": True, "updated": updated})

# teachers/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Class, Quiz, Question, Option, StudentAnswer

@login_required
def create_quiz(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)

    if request.method == "POST":
        action = request.POST.get("action")
        quiz_type = request.POST.get("quiz_type", "quiz")
        quiz_title = request.POST.get("title", "Quiz") 
        description = request.POST.get("description", "")
        duration = int(request.POST.get("duration", 0))  # in minutes

        quiz = Quiz.objects.create(
            class_obj=class_obj,
            title=quiz_title,
            quiz_type=quiz_type,
            description=description,
            duration=duration,
            created_by=request.user,
            status="draft" if action == "draft" else "published"
        )

        # Notifications only if published
        if quiz.status == "published":
            StreamNotification.objects.create(
                user=request.user,
                class_obj=class_obj,
                quiz=quiz,
                message=f"{request.user.get_full_name()} posted a new quiz: {quiz.title}"
            )
            for student in class_obj.students.all():
                StreamNotification.objects.create(
                    user=student,
                    class_obj=class_obj,
                    quiz=quiz,
                    message=f"New quiz '{quiz.title}' has been posted by {request.user.get_full_name()}!"
                )
            messages.success(request, "Quiz created and notifications sent!")
        else:
            messages.info(request, "Quiz saved as draft. You can edit and publish later.")

        # (Questions saving logic dito, same as before...)

        if quiz.status == "draft":
            return redirect("teachers:edit_quiz", quiz_id=quiz.id)
        else:
            return redirect("teachers:subject", id=class_obj.id)

    return render(request, "teachers/quiz.html", {"class_obj": class_obj})


@login_required
def grade_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    answers = StudentAnswer.objects.filter(question__quiz=quiz).select_related("student", "question")

    if request.method == "POST":
        for ans in answers:
            score = request.POST.get(f"score_{ans.id}")
            if score is not None:
                ans.score = float(score)
                ans.save()
        messages.success(request, "Scores updated successfully!")
        return redirect("teachers:subject", class_id=quiz.class_obj.id)

    return render(request, "grade_quiz.html", {"quiz": quiz, "answers": answers})

from students.models import StudentQuizAttempt

@login_required
def quiz_detail(request, class_id, quiz_id):
    class_obj = get_object_or_404(Class, pk=class_id)
    quiz = get_object_or_404(Quiz, pk=quiz_id, class_obj=class_obj)

    # All students in the class
    students = class_obj.students.all()

    # Students who turned in
    turned_in_attempts = StudentQuizAttempt.objects.filter(
        quiz=quiz, status="completed"
    ).select_related("student")

    turned_in_students = [a.student for a in turned_in_attempts]

    # Missing students
    missing_students = students.exclude(id__in=[s.id for s in turned_in_students])

    # Load all answers for this quiz
    student_answers = StudentAnswer.objects.filter(
        student__in=turned_in_students, quiz=quiz
    ).select_related("question", "student", "selected_option")

    # ✅ Store answers in dictionary {"studentId_questionId": answer}
   # ✅ Build nested dictionary answers[student_id][question_id] = answer
    answers = {}
    for ans in student_answers:
        if ans.student_id not in answers:
            answers[ans.student_id] = {}
        answers[ans.student_id][ans.question_id] = ans


    # ✅ Compute total integer scores per student
    total_scores = {}
    for ans in student_answers:
        total_scores[ans.student_id] = total_scores.get(ans.student_id, 0) + int(ans.score)
    # ✅ 1️⃣ Return ALL quiz scores to students
    if request.method == "POST" and "return_scores" in request.POST:
        for student in turned_in_students:
            StreamNotification.objects.create(
                user=student,
                class_obj=class_obj,
                quiz=quiz,
                message=f"Your quiz '{quiz.title}' results have been returned by {request.user.get_full_name()}."
            )
        messages.success(request, "All scores have been returned and students notified.")
        return redirect("teachers:quiz_detail", class_id=class_obj.id, quiz_id=quiz.id)

    # ✅ Handle scoring submission (integer only)
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        question_id = request.POST.get("question_id")
        score = request.POST.get("score")

        if student_id and question_id:
            key = f"{student_id}_{question_id}"
            answer = answers.get(key)
            if answer:
                answer.score = int(score or 0)
                answer.save()

                # ✅ Create a StreamNotification for that student
                StreamNotification.objects.create(
                    user=answer.student,
                    class_obj=class_obj,
                    quiz=quiz,
                    message=f"Your quiz '{quiz.title}' has been graded by {request.user.get_full_name()}."
                )

                messages.success(request, "Score saved and student notified!")

        return redirect("teachers:quiz_detail", class_id=class_obj.id, quiz_id=quiz.id)


    return render(request, "teachers/quiz_detail.html", {
        "class_obj": class_obj,
        "quiz": quiz,
        "turned_in_attempts": turned_in_attempts,
        "missing_students": missing_students,
        "answers": answers,
        "total_scores": total_scores,
    })


# teachers/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import ParentInvite, Parent
from utils.gmail_oauth import send_oauth_email

User = get_user_model()


@login_required
def student_detail(request, user_id):
    student = get_object_or_404(User, id=user_id)
    invites = student.parent_invites.all()
    return render(request, "teachers/student_detail.html", {
        "student": student,
        "invites": invites
    })

@login_required
def invite_parent(request, user_id):
    if request.method == "POST":
        parent_email = request.POST.get("parent_email")
        student = get_object_or_404(User, id=user_id)
        teacher = request.user

        # Prevent duplicate pending invites
        existing_invite = ParentInvite.objects.filter(
            student=student,
            parent_email=parent_email,
            accepted=False
        ).first()
        if existing_invite:
            messages.warning(request, "An invitation has already been sent to this email.")
            return redirect("teachers:student_detail", user_id=student.id)

        invite = ParentInvite.objects.create(
            student=student,
            parent_email=parent_email,
            invited_by=teacher
        )

        # ✅ Use secure token instead of ID
        accept_url = request.build_absolute_uri(
            reverse("teachers:accept_parent_invite", args=[invite.token])
        )

        subject = f"Parent Access Invitation for {student.get_full_name()}"
        text_content = (
            f"You have been invited by {teacher.get_full_name()} to view "
            f"{student.get_full_name()}'s academic progress.\n\nAccept here: {accept_url}"
        )

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Hello!</h2>
            <p>You have been invited by <strong>{teacher.get_full_name()}</strong> 
               to view <strong>{student.get_full_name()}</strong>'s academic progress.</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{accept_url}" 
                   style="background-color: #0d6efd; color: white; padding: 12px 25px;
                          text-decoration: none; border-radius: 5px; font-weight: bold;">
                   Accept Invitation
                </a>
            </p>
            <p>If the button doesn't work, copy and paste this URL into your browser:</p>
            <p><a href="{accept_url}">{accept_url}</a></p>
            <p>Thank you!</p>
        </body>
        </html>
        """

        send_oauth_email(
            to_email=parent_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            reply_to=teacher.email,
        )

        messages.success(request, f"Invitation sent to {parent_email}")
        return redirect("teachers:student_detail", user_id=student.id)

    return redirect("teachers:student_detail", user_id=user_id)


@login_required
def accept_parent_invite(request, token):
    invite = get_object_or_404(ParentInvite, token=token)

    # ✅ Check logged-in user matches invited email
    if request.user.email.lower() != invite.parent_email.lower():
        messages.error(
            request,
            f"This invitation was sent to {invite.parent_email}. "
            f"You are logged in as {request.user.email}. Please log in with the correct account."
        )
        return redirect("accounts:login")

    if invite.accepted:
        messages.info(request, "This invitation has already been accepted.")
        return redirect("parents:dashboard")

    # ✅ Create or get Parent profile
    parent, created = Parent.objects.get_or_create(user=request.user)
    parent.students.add(invite.student)
    parent.save()

    # ✅ Mark invite as accepted
    invite.accepted = True
    invite.save()

    # ===============================
    # 📧 1. Send confirmation to parent
    # ===============================
    subject = "Parent Access Confirmed"
    text_content = (
        f"Hello {request.user.get_full_name()},\n\n"
        f"You have successfully accepted the invitation to monitor {invite.student.get_full_name()}.\n\n"
        "You can now log in anytime to track updates.\n\nThank you!"
    )
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Access Confirmed 🎉</h2>
        <p>Hello <strong>{request.user.get_full_name()}</strong>,</p>
        <p>You have successfully accepted the invitation to monitor 
           <strong>{invite.student.get_full_name()}</strong>'s academic progress.</p>
        <p>You can now log in anytime to track updates.</p>
        <p style="margin-top:20px;">Thank you!</p>
    </body>
    </html>
    """

    send_oauth_email(
        to_email=invite.parent_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )

    # ===============================
    # 📧 2. Notify teacher who sent invite
    # ===============================
    teacher = invite.invited_by
    teacher_subject = f"Parent Accepted Invitation for {invite.student.get_full_name()}"
    teacher_text = (
        f"Hello {teacher.get_full_name()},\n\n"
        f"The parent {request.user.get_full_name()} ({request.user.email}) has accepted "
        f"your invitation to monitor {invite.student.get_full_name()}.\n\n"
        "They can now access the Parent Dashboard and view linked student progress."
    )
    teacher_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Invitation Accepted ✅</h2>
        <p>Hello <strong>{teacher.get_full_name()}</strong>,</p>
        <p>The parent <strong>{request.user.get_full_name()}</strong> 
           (<a href="mailto:{request.user.email}">{request.user.email}</a>) 
           has accepted your invitation to monitor 
           <strong>{invite.student.get_full_name()}</strong>.</p>
        <p>They can now access the Parent Dashboard and view linked student updates.</p>
        <p style="margin-top:20px;">Regards,<br>CMU Smart LMS</p>
    </body>
    </html>
    """

    send_oauth_email(
        to_email=teacher.email,
        subject=teacher_subject,
        text_content=teacher_text,
        html_content=teacher_html,
    )

    # ✅ Success message and redirect
    messages.success(
        request,
        f"Successfully linked to {invite.student.get_full_name()}! Welcome to your parent dashboard."
    )
    return redirect("parents:dashboard")


# views.py
import os
import json
import openai
from openai import OpenAIError  # 🔹 Correct import
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Quiz, Question, Class

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_mock_questions(topic, num_questions=5):
    """Generate placeholder multiple-choice questions based on topic."""
    mock_questions = []
    for i in range(1, num_questions + 1):
        mock_questions.append(
            f"{i}. What is a basic fact about {topic}?\n"
            f"A) Option A\n"
            f"B) Option B\n"
            f"C) Option C\n"
            f"D) Option D\n"
            f"Answer: A\n"
        )
    return "\n".join(mock_questions)

@csrf_exempt
def generate_ai_questions(request, class_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            topic = data.get("topic")

            if not topic:
                return JsonResponse({"error": "Topic is required"}, status=400)

            # Attempt AI call
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": f"Generate 5 multiple choice questions about {topic}. Each question should have 4 choices (A-D) and the correct answer marked."}]
                )
                ai_output = response.choices[0].message.content.strip()
            except Exception:
                # Fallback to mock questions
                ai_output = generate_mock_questions(topic)

            # ✅ Return AI-generated content only
            return JsonResponse({
                "content": ai_output
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

@login_required
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    classes = Class.objects.filter(teacher=request.user)
    class_obj = assignment.class_obj  # ✅ get related class

    if request.method == 'POST':
        assignment.title = request.POST.get('title')
        assignment.instructions = request.POST.get('instructions')
        assignment.points = request.POST.get('points')
        assignment.due_date = request.POST.get('due_date')
        assignment.due_time = request.POST.get('due_time')
        assignment.class_for_id = request.POST.get('class_for')

        if 'file' in request.FILES:
            assignment.file = request.FILES['file']

        assignment.save()
        messages.success(request, "✅ Assignment updated successfully.")
        return redirect('teachers:subject',  id=class_obj.id)

    return render(request, 'teachers/assignment_edit.html', {
        'assignment': assignment,
        'classes': classes,
        'class_obj': class_obj,  # ✅ pass this to template
    })

@login_required
def remove_assignment_file(request, id):
    assignment = get_object_or_404(Assignment, id=id)
    if assignment.file:
        assignment.file.delete()
        assignment.file = None
        assignment.save()
        messages.success(request, "🗑️ Attachment removed.")
    return redirect('teachers:edit_assignment', id)

@login_required
def edit_quiz(request, id):
    quiz = get_object_or_404(Quiz, pk=id)

    if request.method == 'POST':
        form = Quiz(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz updated successfully.")
            return redirect('teachers:subject', quiz.class_obj.id)
    else:
        form = Quiz(instance=quiz)

    return render(request, 'teachers/edit_quiz.html', {
        'form': form,
        'quiz': quiz
    })

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from .models import Class, AttendanceSession, AttendanceRecord, StreamNotification

from django.urls import reverse

@login_required
def start_attendance(request, class_id):
    class_obj = get_object_or_404(Class, pk=class_id, teacher=request.user)
    
    if request.method == "POST":
        lat = float(request.POST.get("latitude", 0.0))
        lng = float(request.POST.get("longitude", 0.0))
        radius = float(request.POST.get("radius_m", 50))
        duration_minutes = int(request.POST.get("duration_minutes", 30))  # default 30 mins

        # Create AttendanceSession
        session = AttendanceSession.objects.create(
            class_obj=class_obj,
            teacher=request.user,
            latitude=lat,
            longitude=lng,
            radius_m=radius,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=duration_minutes),
            is_active=True
        )

        # Create AttendanceRecord for each student
        for student in class_obj.students.all():
            AttendanceRecord.objects.create(session=session, student=student)

            # Notify students
            StreamNotification.objects.create(
                user=student,
                class_obj=class_obj,
                attendance_session=session,
                message=f"New attendance session started in {class_obj.class_name}. Click to check in!"
            )

        # ✅ Notify teacher as well so it appears in their Recent Activity
        StreamNotification.objects.create(
            user=request.user,
            class_obj=class_obj,
            attendance_session=session,
            message=f"Attendance session started in {class_obj.class_name}."
        )

        messages.success(request, "Attendance session started successfully!")
        
        # Redirect teacher to notifications/Recent Activity section
        return redirect(reverse('teachers:subject', kwargs={'id': class_obj.id}) + "#recent-activity")

    return render(request, "teachers/start_attendance.html", {"class_obj": class_obj})

@login_required
def attendance_session_detail(request, session_id):
    session = get_object_or_404(AttendanceSession, pk=session_id, teacher=request.user)
    records = session.records.select_related('student').all()

    return render(request, "teachers/attendance_session_detail.html", {
        "session": session,
        "records": records,
    })
