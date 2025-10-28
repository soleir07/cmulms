from django import template
from teachers.models import StudentAnswer

register = template.Library()

@register.filter
def get_answer(question, student):
    try:
        ans = StudentAnswer.objects.get(question=question, student=student)
        # return appropriate field depending on what type of answer it is
        if ans.selected_option:
            return ans.selected_option.text
        elif ans.text_answer:
            return ans.text_answer
        else:
            return None
    except StudentAnswer.DoesNotExist:
        return None

@register.filter
def get_answer_object(question, user):
    """Return the StudentAnswer object for a given question and student"""
    return StudentAnswer.objects.filter(question=question, student=user).first()
