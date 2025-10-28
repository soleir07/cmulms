from django import template
from django.db.models import Q

register = template.Library()

@register.simple_tag
def get_student_private_comments(private_comments_queryset, student, teacher_user):
    """
    Filters a queryset of private comments to show only those relevant to a specific student
    and the current teacher.
    Args:
        private_comments_queryset: The queryset of private comments.
        student: The student object.
        teacher_user: The teacher user object (request.user).
    """
    # The private_comments_queryset from the view already contains comments relevant to the teacher.
    # This tag now filters that queryset for comments specifically involving the 'student' object.
    return private_comments_queryset.filter(
        Q(user=student, recipient=teacher_user) |
        Q(user=teacher_user, recipient=student) |
        Q(user=student, recipient=student) # Include comments from student to themselves (if applicable, though unlikely for private)
    ).order_by('created_at')