# teachers/urls.py
from django.urls import path
from . import views

app_name = 'teachers'

urlpatterns = [
    path('dashboard/', views.teacherdashboard, name='dashboard'),
    path('calendar/', views.calendar, name='calendar'),
    path("announcement/", views.announcement_list, name="announcement_list"),
    path("announcement/<int:id>/", views.announcement_detail, name="announcement_detail"),
    path("announcement/<int:id>/edit/", views.announcement_edit, name="announcement_edit"),
    path("announcement/<int:id>/delete/", views.announcement_delete, name="announcement_delete"),
    path('subject/', views.subject, name='subject'),
    
    #Assignment Path
    path("assignment/form/<int:id>/", views.assignment_form, name="assignment_form"),
    path("assignment/<int:assignment_id>/", views.assignment_detail, name="assignment_detail"),
    path("assignment/<int:assignment_id>/submit/", views.submit_assignment, name="submit_assignment"),
    path("assignment/<int:assignment_id>/delete/", views.delete_assignment, name="delete_assignment"),
    path('assignment/<int:assignment_id>/edit/', views.edit_assignment, name='edit_assignment'),
    path('quiz/<int:id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('assignment/<int:id>/remove-file/', views.remove_assignment_file, name='remove_assignment_file'),
    path("assignment/<int:assignment_id>/post-class-comment/", views.post_class_comment, name="post_class_comment"),
    path('delete_notification/<int:id>/', views.delete_notification, name='delete_notification'),

    
    #Notification
    path("subject/<int:class_id>/clear-notifications/", views.clear_notifications, name="clear_notifications"),
    path('notification/redirect/<int:notification_id>/', views.notification_redirect, name='notification_redirect'),
    #Class Path
    path("create-class/", views.create_class, name="create_class"),
    path('subject/<int:id>/', views.subject, name='subject'),
    #Gradebook
    path("class/<int:class_id>/grades/", views.class_grades, name="class_grades"),
    path("class/<int:class_id>/grades/export/", views.export_grades, name="export_grades"),
    path("class/<int:class_id>/grades/import/", views.import_grades, name="import_grades"),
    path("class/<int:class_id>/grade/<int:submission_id>/", views.update_grade, name="update_grade"),
    # Archive/restore
    path("subject/<int:class_id>/archive/", views.archive_class, name="archive_class"),
    path("subject/<int:class_id>/restore/", views.restore_archived_class, name="restore_archived_class"),
    path("archived-classes/", views.archived_classes, name="archived_classes"),

    path("subject/<int:class_id>/edit/", views.edit_class, name="edit_class"),
    path("messages/", views.messages_inbox, name="messages_inbox"),       # just contacts, no chat open
    path("messages/<int:user_id>/", views.conversation, name="conversation"),  # open specific chat
    path("submissions/bulk-return/", views.bulk_return_submissions, name="bulk_return_submissions"),

    # Quiz-related routes
    path("class/<int:class_id>/quiz/create/", views.create_quiz, name="create_quiz"),
    path("quiz/<int:quiz_id>/grade/", views.grade_quiz, name="grade_quiz"), # NEW quiz path
    path("class/<int:class_id>/quiz/<int:quiz_id>/", views.quiz_detail, name="quiz_detail"),
    path("class/<int:class_id>/generate_ai_questions/", views.generate_ai_questions, name="generate_ai_questions"),


    path("student/<int:user_id>/", views.student_detail, name="student_detail"),
    path("student/<int:user_id>/invite-parent/", views.invite_parent, name="invite_parent"),
    path("accept-parent-invite/<uuid:token>/", views.accept_parent_invite, name="accept_parent_invite"),

    # Attendance routes
    path('subject/<int:class_id>/start-attendance/', views.start_attendance, name='start_attendance'),
    path('attendance-session/<int:session_id>/', views.attendance_session_detail, name='attendance_session_detail'),
]
