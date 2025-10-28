from django.urls import path
from . import views

app_name = 'parents'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path("calendar/", views.calendar, name="calendar"),
    path("announcements/", views.announcements, name="announcements"),
    path("student/<int:student_id>/progress/", views.student_progress, name="student_progress"),
    path('conversation/', views.conversation, name='conversation'),
    path('conversation/<int:user_id>/', views.conversation, name='conversation'),


    
]