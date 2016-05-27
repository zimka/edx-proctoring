from django.core.management.base import BaseCommand
from edx_proctoring.models import ProctoredExamStudentAttempt, ProctoredExamStudentAttemptStatus
from xmodule.modulestore.django import modulestore
from datetime import timedelta, datetime


class Command(BaseCommand):
    """
    Django Management command to force a background check of all possible notifications
    """

    def handle(self, *args, **options):
        courses = modulestore().get_courses()
        for course in courses:
            course_id = course.id.html_id()
            all_exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(course_id)
            for exam_attempt in all_exam_attempts:
                if exam_attempt.status == ProctoredExamStudentAttemptStatus.created:
                    if exam_attempt.modified + timedelta(0.5) < datetime.now():
                        print "Exam attempt with status created (last modified at {0}, course id: {1}, user_id: {2})" \
                              "will be deleted".format(exam_attempt.modified, course_id, exam_attempt.user_id)
                        exam_attempt.delete_exam_attempt()
