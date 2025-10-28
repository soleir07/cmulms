from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import school_admin_required
from accounts.models import User
from .models import SchoolClass, Announcement
from .forms import TeacherForm, StudentForm, SchoolClassForm, AnnouncementForm
from teachers.models import Class 
# === DASHBOARD ===
@login_required
@school_admin_required
def dashboard(request):
    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()  # ✅ added
    classes = Class.objects.count()
    announcements = Announcement.objects.count()

    return render(request, "admins/dashboard.html", {
        "teachers": teachers,
        "students": students,
        "parents": parents,              # ✅ added
        "classes": classes,
        "announcements": announcements
    })

# === TEACHER CRUD ===
@login_required
@school_admin_required
def teacher_list(request):
    teachers = User.objects.filter(role="teacher")
    return render(request, "admins/teacher_list.html", {"teachers": teachers})

@login_required
@school_admin_required
def teacher_add(request):
    if request.method == "POST":
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.role = "teacher"
            teacher.set_password(form.cleaned_data["password"])
            teacher.save()
            return redirect("admins:teacher_list")
    else:
        form = TeacherForm()
    return render(request, "admins/teacher_form.html", {"form": form})

@login_required
@school_admin_required
def teacher_delete(request, id):
    teacher = get_object_or_404(User, id=id, role="teacher")
    teacher.delete()
    return redirect("admins:teacher_list")

@login_required
@school_admin_required
def teacher_detail(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id, role="teacher")
    classes = teacher.created_classes.all()  # ✅ assumes teachers.Class has ForeignKey(teacher=User)

    return render(request, "admins/teacher_detail.html", {
        "teacher": teacher,
        "classes": classes,
    })
# === STUDENT CRUD ===
@login_required
@school_admin_required
def student_list(request):
    students = User.objects.filter(role="student")
    return render(request, "admins/student_list.html", {"students": students})

@login_required
@school_admin_required
def student_add(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save(commit=False)
            student.role = "student"

            # Set password only if entered
            password = form.cleaned_data["password"]
            if password:
                student.set_password(password)
            student.save()

            # Link parents
            parent_emails = form.cleaned_data.get("parent_emails", "")
            if parent_emails:
                emails = [e.strip() for e in parent_emails.split(",")]
                for email in emails:
                    try:
                        parent_user = User.objects.get(email=email, role="parent")
                        parent_profile = parent_user.parent_profile
                        parent_profile.students.add(student)
                    except User.DoesNotExist:
                        pass  # skip non-existing parent emails

            return redirect("admins:student_list")
    else:
        form = StudentForm()
    return render(request, "admins/student_form.html", {"form": form})


@login_required
@school_admin_required
def student_edit(request, student_id):
    student = get_object_or_404(User, id=student_id, role="student")
    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            student = form.save(commit=False)

            # Update password only if entered
            password = form.cleaned_data["password"]
            if password:
                student.set_password(password)
            student.save()

            # Clear previous parent links
            student.linked_parents.clear()

            # Link new parents
            parent_emails = form.cleaned_data.get("parent_emails", "")
            if parent_emails:
                emails = [e.strip() for e in parent_emails.split(",")]
                for email in emails:
                    try:
                        parent_user = User.objects.get(email=email, role="parent")
                        parent_profile = parent_user.parent_profile
                        parent_profile.students.add(student)
                    except User.DoesNotExist:
                        pass

            return redirect("admins:student_detail", student_id=student.id)
    else:
        # Pre-fill parent emails
        parent_emails = ", ".join([p.user.email for p in student.linked_parents.all()])
        form = StudentForm(instance=student, initial={"parent_emails": parent_emails})

    return render(request, "admins/student_form.html", {"form": form})

@login_required
@school_admin_required
def student_delete(request, id):
    student = get_object_or_404(User, id=id, role="student")
    student.delete()
    return redirect("admins:student_list")

# === STUDENT DETAIL VIEW ===
@login_required
@school_admin_required
def student_detail(request, student_id):
    student = get_object_or_404(User, id=student_id, role="student")
    classes = student.enrolled_classes.all()  # ✅ M2M relation from your model

    return render(request, "admins/student_detail.html", {
        "student": student,
        "classes": classes,
    })
# === CLASS CRUD ===
@login_required
@school_admin_required
def class_list(request):
    classes = SchoolClass.objects.all()
    return render(request, "admins/class_list.html", {"classes": classes})

@login_required
@school_admin_required
def class_add(request):
    if request.method == "POST":
        form = SchoolClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("class_list")
    else:
        form = SchoolClassForm()
    return render(request, "admins/class_form.html", {"form": form})

@login_required
@school_admin_required
def class_delete(request, id):
    c = get_object_or_404(SchoolClass, id=id)
    c.delete()
    return redirect("class_list")

# === ANNOUNCEMENTS ===
@login_required
@school_admin_required
def announcement_list(request):
    announcements = Announcement.objects.all().order_by("-created_at")
    return render(request, "admins/announcement_list.html", {"announcements": announcements})

@login_required
@school_admin_required
def announcement_add(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            return redirect("announcement_list")
    else:
        form = AnnouncementForm()
    return render(request, "admins/announcement_form.html", {"form": form})

# admins/views.py
from .forms import ParentForm, ParentStudentForm
from .models import ParentStudent

# === PARENT CRUD ===
@login_required
@school_admin_required
def parent_list(request):
    parents = User.objects.filter(role="parent")
    return render(request, "admins/parent_list.html", {"parents": parents})

@login_required
@school_admin_required
def parent_add(request):
    if request.method == "POST":
        form = ParentForm(request.POST)
        if form.is_valid():
            parent = form.save(commit=False)
            parent.role = "parent"
            parent.set_password(form.cleaned_data["password"])
            parent.save()
            return redirect("parent_list")
    else:
        form = ParentForm()
    return render(request, "admins/parent_form.html", {"form": form})

@login_required
@school_admin_required
def parent_delete(request, id):
    parent = get_object_or_404(User, id=id, role="parent")
    parent.delete()
    return redirect("parent_list")

# === LINK PARENT TO STUDENT ===
@login_required
@school_admin_required
def parent_student_list(request):
    links = ParentStudent.objects.all()
    return render(request, "admins/parent_student_list.html", {"links": links})

@login_required
@school_admin_required
def parent_student_add(request):
    if request.method == "POST":
        form = ParentStudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("parent_student_list")
    else:
        form = ParentStudentForm()
    return render(request, "admins/parent_student_form.html", {"form": form})

@login_required
@school_admin_required
def parent_student_delete(request, id):
    link = get_object_or_404(ParentStudent, id=id)
    link.delete()
    return redirect("parent_student_list")

from django.http import JsonResponse
from django.contrib.auth import get_user_model

User = get_user_model()

def user_role_stats(request):
    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()

    total = teachers + students + parents or 1  # avoid division by zero

    data = {
        "teachers": round((teachers / total) * 100, 2),
        "students": round((students / total) * 100, 2),
        "parents": round((parents / total) * 100, 2),
        "total": total,
    }
    return JsonResponse(data)

import csv
import io
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from django.db import models
from teachers.models import Class  # if your Class model is named differently, adjust
from teachers.models import Class as TeacherClass  # you use teachers.Class in other views
from .models import Announcement  # whatever you already have
from teachers.models import Quiz, StudentAnswer  # adjust imports to match your project structure
from teachers.models import Submission, Assignment  # if these live in admins, change accordingly

def reports(request):
    """
    Render Reports page with data for charts and tables.
    """
    User = get_user_model()

    # --- User role counts ---
    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()
    total_users = teachers + students + parents

    user_counts = {
        "teachers": teachers,
        "students": students,
        "parents": parents,
        "total": total_users or 0,
    }

    # --- Classes and students per class ---
    # NOTE: you appear to have Class model in teachers app and also SchoolClass in admins.
    # We'll read from teachers.Class (rename if needed).
    classes_qs = TeacherClass.objects.filter(is_archived=False).order_by("class_name")
    class_labels = []
    students_per_class = []
    for c in classes_qs:
        class_labels.append(str(c))
        students_per_class.append(c.students.count())

    # --- Quizzes per class ---
    quizzes_labels = []
    quizzes_data = []
    for c in classes_qs:
        qcount = c.quizzes.count()
        quizzes_labels.append(str(c))
        quizzes_data.append(qcount)

    # --- Average quiz score per class (across quizzes belonging to class) ---
    avg_score_labels = []
    avg_scores = []
    for c in classes_qs:
        answers = StudentAnswer.objects.filter(quiz__class_obj=c).exclude(score__isnull=True)
        if answers.exists():
            avg = answers.aggregate(models.Avg('score'))['score__avg'] or 0
        else:
            avg = 0
        avg_score_labels.append(str(c))
        avg_scores.append(round(avg, 2))

    # --- Submission status summary ---
    submission_counts = {
    "assigned": Submission.objects.filter(status="assigned").count(),
    "turned_in": Submission.objects.filter(status="turned_in").count(),
    "missing": Submission.objects.filter(status="missing").count(),
    # graded is not part of 'status' choices, so use grade presence
    "graded": Submission.objects.filter(grade__isnull=False).count(),
}


    # Pass context
    context = {
        "user_counts": user_counts,
        "class_labels": class_labels,
        "students_per_class": students_per_class,
        "quizzes_labels": quizzes_labels,
        "quizzes_data": quizzes_data,
        "avg_score_labels": avg_score_labels,
        "avg_scores": avg_scores,
        "submission_counts": submission_counts,
    }

    return render(request, "admins/reports.html", context)


def reports_export_csv(request):
    """
    Export report summary as CSV. This will include user summary, classes, quizzes and avg scores.
    """
    User = get_user_model()

    # Prepare CSV
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # Header + timestamp
    writer.writerow(["CMU LMS — Reports Export"])
    writer.writerow(["Generated at", timezone.now().isoformat()])
    writer.writerow([])

    # User summary
    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()
    writer.writerow(["User Summary"])
    writer.writerow(["Role", "Count"])
    writer.writerow(["Teachers", teachers])
    writer.writerow(["Students", students])
    writer.writerow(["Parents", parents])
    writer.writerow([])

    # Classes summary
    writer.writerow(["Classes Summary"])
    writer.writerow(["Class", "Students", "Quizzes", "Avg Quiz Score"])
    classes_qs = TeacherClass.objects.filter(is_archived=False)
    for c in classes_qs:
        student_count = c.students.count()
        quiz_count = c.quizzes.count()
        answers = StudentAnswer.objects.filter(quiz__class_obj=c).exclude(score__isnull=True)
        avg = 0
        if answers.exists():
            avg = answers.aggregate(models.Avg('score'))['score__avg'] or 0
        writer.writerow([str(c), student_count, quiz_count, round(avg, 2)])
    writer.writerow([])

    # Submission summary
    writer.writerow(["Submission Summary"])
    writer.writerow(["Status", "Count"])
    writer.writerow(["Assigned", Submission.objects.filter(status="assigned").count()])
    writer.writerow(["Turned In", Submission.objects.filter(status="turned_in").count()])
    writer.writerow(["Missing", Submission.objects.filter(status="missing").count()])
    writer.writerow(["Graded", Submission.objects.filter(grade__isnull=False).count()])

    # Return CSV response
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    filename = f"cmu_reports_{timezone.now().date()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def reports_export_pdf(request):
    """
    Export bare-bones PDF summary using reportlab.
    Install reportlab: pip install reportlab
    """
    # Prepare data similar to CSV
    User = get_user_model()
    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()
    classes_qs = TeacherClass.objects.filter(is_archived=False)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("CMU LMS — Reports", styles['Title']))
    elems.append(Paragraph(f"Generated at: {timezone.now().isoformat()}", styles['Normal']))
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("User Summary", styles['Heading2']))
    user_table = [["Role", "Count"], ["Teachers", teachers], ["Students", students], ["Parents", parents]]
    t = Table(user_table, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3F51B5")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1, -1), 'Helvetica'),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Classes Summary", styles['Heading2']))
    class_table_data = [["Class", "Students", "Quizzes", "Avg Score"]]
    for c in classes_qs:
        student_count = c.students.count()
        quiz_count = c.quizzes.count()
        answers = StudentAnswer.objects.filter(quiz__class_obj=c).exclude(score__isnull=True)
        avg = 0
        if answers.exists():
            avg = answers.aggregate(models.Avg('score'))['score__avg'] or 0
        class_table_data.append([str(c), str(student_count), str(quiz_count), str(round(avg,2))])

    t2 = Table(class_table_data, hAlign='LEFT', colWidths=[140, 60, 60, 60])
    t2.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#5C6BC0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
    ]))
    elems.append(t2)

    doc.build(elems)
    pdf = buffer.getvalue()
    buffer.close()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cmu_reports_{timezone.now().date()}.pdf"'
    return response

from django.http import JsonResponse

def reports_data(request):
    # Replicate the logic from reports view to provide the required data
    User = get_user_model()

    teachers = User.objects.filter(role="teacher").count()
    students = User.objects.filter(role="student").count()
    parents = User.objects.filter(role="parent").count()
    total_users = teachers + students + parents

    user_counts = {
        "teachers": teachers,
        "students": students,
        "parents": parents,
        "total": total_users or 0,
    }

    classes_qs = TeacherClass.objects.filter(is_archived=False).order_by("class_name")
    class_labels = []
    students_per_class = []
    for c in classes_qs:
        class_labels.append(str(c))
        students_per_class.append(c.students.count())

    avg_score_labels = []
    avg_scores = []
    for c in classes_qs:
        answers = StudentAnswer.objects.filter(quiz__class_obj=c).exclude(score__isnull=True)
        if answers.exists():
            avg = answers.aggregate(models.Avg('score'))['score__avg'] or 0
        else:
            avg = 0
        avg_score_labels.append(str(c))
        avg_scores.append(round(avg, 2))

    data = {
        "user_counts": user_counts,
        "class_labels": class_labels,
        "students_per_class": students_per_class,
        "avg_score_labels": avg_score_labels,
        "avg_scores": avg_scores,
    }
    return JsonResponse(data)
