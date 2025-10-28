import requests
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import User
from allauth.socialaccount.providers import registry


def login_view(request):
    if request.method == 'POST':
        # --- 1. Check reCAPTCHA ---
        recaptcha_response = request.POST.get('g-recaptcha-response')
        data = {
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response
        }
        verify = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = verify.json()

        if not result.get('success'):
            return render(request, 'accounts/login.html', {
                'error': 'Please verify that you are not a robot.'
            })

        # --- 2. Normal username/password authentication ---
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('accounts:redirect_dashboard')
        else:
            return render(request, 'accounts/login.html', {
                'error': 'Invalid credentials'
            })

    # GET request
    return render(request, 'accounts/login.html')  # no socialaccount context needed


@login_required
def redirect_dashboard(request):
    user = request.user

    # Superuser or admin role
    if user.is_superuser or user.role == "admin":
        return redirect("/admin/")

    # If no role yet, send to role selection
    if not user.role:
        return redirect("accounts:choose_role")

    # Role-based dashboards
    if user.role == "teacher":
        return redirect("teachers:dashboard")
    elif user.role == "student":
        return redirect("students:dashboard")
    elif user.role == "parent":
        from teachers.models import Parent
        Parent.objects.get_or_create(user=user)
        return redirect("parents:dashboard")
    elif user.role == "school_admin":
        return redirect("admins:dashboard")  # fixed ✅

    # Default fallback
    return redirect("accounts:choose_role")
    
@login_required
def choose_role(request):
    if request.method == "POST":
        role = request.POST.get("role")
        if role in ["student", "teacher", "parent"]:
            request.user.role = role
            request.user.save()
            return redirect("accounts:redirect_dashboard")  # send back to dashboard redirect
    return render(request, "accounts/choose_role.html")

# accounts/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import Profile
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def settings_view(request):
    user = request.user
    profile = user.profile
    parent_email = None  # new variable

    # --- Determine parent/child email relationship ---
    if user.role == "student":
        parent = user.linked_parents.first()
        if parent:
            parent_email = parent.user.email
    elif user.role == "parent":
        student = user.parent_profile.students.first()
        if student:
            parent_email = student.email

    if request.method == "POST":
        action = request.POST.get("action")

        # --- Change Avatar ---
        if action == "avatar" and request.FILES.get("avatar"):
            profile.avatar = request.FILES["avatar"]
            profile.avatar_url = None  # clear Google URL if new upload
            profile.save()
            messages.success(request, "Profile photo updated successfully.")
            return redirect("accounts:settings")

        # --- Change Email ---
        elif action == "email":
            new_email = request.POST.get("email")

            # If the logged-in user is a student → update parent's email
            if user.role == "student":
                parent = user.linked_parents.first()
                if parent:
                    parent.user.email = new_email
                    parent.user.save()
                    messages.success(request, "Parent email updated successfully.")
                else:
                    messages.error(request, "No parent linked to your account yet.")

            # If logged-in user is a parent → update child's email
            elif user.role == "parent":
                student = user.parent_profile.students.first()
                if student:
                    student.email = new_email
                    student.save()
                    messages.success(request, "Child email updated successfully.")
                else:
                    messages.error(request, "No student linked to your account yet.")

            # If logged-in user is neither student nor parent → update own email
            else:
                if new_email:
                    user.email = new_email
                    user.save()
                    messages.success(request, "Email updated successfully.")

            return redirect("accounts:settings")

        # --- Change Password ---
        elif action == "password":
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password updated successfully.")
                return redirect("accounts:settings")
            else:
                messages.error(request, "Please correct the error below.")

        # --- Delete Account ---
        elif action == "delete":
            user.delete()
            messages.success(request, "Account deleted.")
            return redirect("home")

    return render(request, "accounts/settings.html", {
        "user": user,
        "parent_email": parent_email,  # send to template
    })
