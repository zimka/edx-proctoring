# pylint: disable=too-many-lines
"""
Data models for the proctoring subsystem
"""

# pylint: disable=model-missing-unicode

from __future__ import absolute_import
import six
import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.db.models.base import ObjectDoesNotExist
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import ugettext as _, ugettext_noop
from jsonfield.fields import JSONField

from model_utils.models import TimeStampedModel

from edx_proctoring.exceptions import (
    UserNotFoundException,
    ProctoredExamNotActiveException,
    AllowanceValueNotAllowedException
)
from opaque_keys.edx.keys import CourseKey
from openedx.core.lib.courses import course_image_url


@six.python_2_unicode_compatible
class ProctoredExam(TimeStampedModel):
    """
    Information about the Proctored Exam.
    """

    course_id = models.CharField(max_length=255, db_index=True)

    # This will be the pointer to the id of the piece
    # of course_ware which is the proctored exam.
    content_id = models.CharField(max_length=255, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # This is the display name of the Exam (Midterm etc).
    exam_name = models.TextField()

    # Time limit (in minutes) that a student can finish this exam.
    time_limit_mins = models.IntegerField()

    # Due date is a deadline to finish the exam
    due_date = models.DateTimeField(null=True)

    # Whether this exam actually is proctored or not.
    is_proctored = models.BooleanField(default=False)

    # Whether this exam is for practice only.
    is_practice_exam = models.BooleanField(default=False)

    # Whether this exam will be active.
    is_active = models.BooleanField(default=False)

    # Whether to hide this exam after the due date
    hide_after_due = models.BooleanField(default=False)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('course_id', 'content_id'),)
        db_table = 'proctoring_proctoredexam'

    def __str__(self):
        # pragma: no cover
        return u"{course_id}: {exam_name} ({active})".format(
            course_id=self.course_id,
            exam_name=self.exam_name,
            active='active' if self.is_active else 'inactive',
        )

    @classmethod
    def get_exam_by_content_id(cls, course_id, content_id):
        """
        Returns the Proctored Exam if found else returns None,
        Given course_id and content_id
        """
        try:
            proctored_exam = cls.objects.get(course_id=course_id, content_id=content_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            proctored_exam = None
        return proctored_exam

    @classmethod
    def get_exam_by_id(cls, exam_id):
        """
        Returns the Proctored Exam if found else returns None,
        Given exam_id (PK)
        """
        try:
            proctored_exam = cls.objects.get(id=exam_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            proctored_exam = None
        return proctored_exam

    @classmethod
    def get_all_exams_for_course(cls, course_id, active_only=False, timed_exams_only=False,
                                 proctored_exams_only=False, dt_expired=False, proctoring_service=False):
        """
        Returns all exams for a give course
        """
        filtered_query = Q(course_id=course_id)

        if active_only:
            filtered_query = filtered_query & Q(is_active=True)
        if timed_exams_only:
            filtered_query = filtered_query & Q(is_proctored=False)
        if proctored_exams_only:
            filtered_query = filtered_query & Q(is_proctored=True) & Q(is_practice_exam=False)
        if dt_expired:
            filtered_query = filtered_query & (Q(due_date__isnull=True) | Q(due_date__gt=datetime.datetime.now()))
        if proctoring_service:
            filtered_query = filtered_query & Q(proctored_exam_params__service=proctoring_service)

        return cls.objects.filter(filtered_query).prefetch_related('proctored_exam_params')

    def _update_extended_exam_params(self, exam_params):
        if 'service' in exam_params and exam_params['service']:
            exam_params['service'] = exam_params['service'].strip() if exam_params['service'].strip() else None
        else:
            exam_params['service'] = None
        return exam_params

    def add_extended_exam_params(self, exam_params):
        exam_params = self._update_extended_exam_params(exam_params)
        exam_params['updated'] = True
        exam_params['exam'] = self
        ProctoredExamParams(**exam_params).save()

    def update_extended_exam_params(self, exam_params):
        exam_params = self._update_extended_exam_params(exam_params)
        exam_params['updated'] = True
        try:
            for attr, value in exam_params.items():
                setattr(self.proctored_exam_params, attr, value)
                self.proctored_exam_params.save()
        except ProctoredExamParams.DoesNotExist:
            self.add_extended_exam_params(exam_params)


class ProctoredExamStudentAttemptStatus(object):
    """
    A class to enumerate the various status that an attempt can have

    IMPORTANT: Since these values are stored in a database, they are system
    constants and should not be language translated, since translations
    might change over time.
    """

    # the student is eligible to decide if he/she wants to pursue credit
    eligible = 'eligible'

    # the attempt record has been created, but the exam has not yet
    # been started
    created = 'created'

    # the student has clicked on the external
    # software download link
    download_software_clicked = 'download_software_clicked'

    # the attempt is ready to start but requires
    # user to acknowledge that he/she wants to start the exam
    ready_to_start = 'ready_to_start'

    # the student has started the exam and is
    # in the process of completing the exam
    started = 'started'

    # the student has completed the exam
    ready_to_submit = 'ready_to_submit'

    #
    # The follow statuses below are considered in a 'completed' state
    # and we will not allow transitions to status above this mark
    #

    # the student declined to take the exam as a proctored exam
    declined = 'declined'

    # the exam has timed out
    timed_out = 'timed_out'

    # the student has submitted the exam for proctoring review
    submitted = 'submitted'

    # the student has submitted the exam for proctoring review
    second_review_required = 'second_review_required'

    # the exam has been verified and approved
    verified = 'verified'

    # the exam has been rejected
    rejected = 'rejected'

    # the exam is believed to be in error
    error = 'error'

    # the course end date has passed
    expired = 'expired'

    # status alias for sending email
    status_alias_mapping = {
        submitted: ugettext_noop('pending'),
        verified: ugettext_noop('satisfactory'),
        rejected: ugettext_noop('unsatisfactory')
    }

    @classmethod
    def is_completed_status(cls, status):
        """
        Returns a boolean if the passed in status is in a "completed" state, meaning
        that it cannot go backwards in state
        """
        return status in [
            cls.declined, cls.timed_out, cls.submitted, cls.second_review_required,
            cls.verified, cls.rejected, cls.error
        ]

    @classmethod
    def is_incomplete_status(cls, status):
        """
        Returns a boolean if the passed in status is in an "incomplete" state.
        """
        return status in [
            cls.eligible, cls.created, cls.download_software_clicked, cls.ready_to_start, cls.started,
            cls.ready_to_submit
        ]

    @classmethod
    def needs_credit_status_update(cls, to_status):
        """
        Returns a boolean if the passed in to_status calls for an update to the credit requirement status.
        """
        return to_status in [
            cls.verified, cls.rejected, cls.declined, cls.submitted, cls.error
        ]

    @classmethod
    def is_a_cascadable_failure(cls, to_status):
        """
        Returns a boolean if the passed in to_status has a failure that needs to be cascaded
        to other unattempted exams.
        """
        return to_status in [
            cls.declined
        ]

    @classmethod
    def get_status_alias(cls, status):
        """
        Returns status alias used in email
        """
        status_alias = cls.status_alias_mapping.get(status, None)

        # Note that the alias is localized here as it is untranslated in the model
        return _(status_alias) if status_alias else ''  # pylint: disable=translation-of-non-string

    @classmethod
    def is_valid_status(cls, status):
        """
        Makes sure that passed in status string is valid
        """
        return cls.is_completed_status(status) or cls.is_incomplete_status(status)


@six.python_2_unicode_compatible
class ProctoredExamReviewPolicy(TimeStampedModel):
    """
    This is how an instructor can set review policies for a proctored exam
    """

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(User)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # policy that will be passed to reviewers
    review_policy = models.TextField()

    def __str__(self):
        # pragma: no cover
        return u"ProctoredExamReviewPolicy: {set_by_user} ({proctored_exam})".format(
            set_by_user=self.set_by_user,
            proctored_exam=self.proctored_exam,
        )

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamreviewpolicy'
        verbose_name = 'Proctored exam review policy'
        verbose_name_plural = "Proctored exam review policies"

    @classmethod
    def get_review_policy_for_exam(cls, exam_id):
        """
        Returns the current exam review policy for the specified
        exam_id or None if none exists
        """

        try:
            return cls.objects.get(proctored_exam_id=exam_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            return None


class ProctoredExamReviewPolicyHistory(TimeStampedModel):
    """
    Archive table to record all policies that were deleted or updated
    """

    # what was the original PK for the Review Policy
    original_id = models.IntegerField(db_index=True)

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(User)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # policy that will be passed to reviewers
    review_policy = models.TextField()

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamreviewpolicyhistory'
        verbose_name = 'proctored exam review policy history'

    def delete(self, *args, **kwargs):
        """
        Don't allow deletions!
        """
        raise NotImplementedError()


# Hook up the post_save signal to record creations in the ProctoredExamReviewPolicyHistory table.
@receiver(pre_save, sender=ProctoredExamReviewPolicy)
def on_review_policy_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        # only for update cases
        original = ProctoredExamReviewPolicy.objects.get(id=instance.id)
        _make_review_policy_archive_copy(original)


# Hook up the pre_delete signal to record creations in the ProctoredExamReviewPolicyHistory table.
@receiver(pre_delete, sender=ProctoredExamReviewPolicy)
def on_review_policy_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_review_policy_archive_copy(instance)


def _make_review_policy_archive_copy(instance):
    """
    Do the copying into the history table
    """

    archive_object = ProctoredExamReviewPolicyHistory(
        original_id=instance.id,
        set_by_user_id=instance.set_by_user_id,
        proctored_exam=instance.proctored_exam,
        review_policy=instance.review_policy,
    )
    archive_object.save()


class ProctoredExamStudentAttemptManager(models.Manager):
    """
    Custom manager
    """
    def get_exam_attempt(self, exam_id, user_id):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(proctored_exam_id=exam_id, user_id=user_id)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_id(self, attempt_id):
        """
        Returns the Student Exam Attempt by the attempt_id else return None
        """
        try:
            exam_attempt_obj = self.get(id=attempt_id)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_code(self, attempt_code):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(attempt_code=attempt_code)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_all_exam_attempts(self, course_id, timed_exams_only=False):
        """
        Returns the Student Exam Attempts for the given course_id.
        """
        filtered_query = Q(proctored_exam__course_id=course_id)

        if timed_exams_only:
            filtered_query = filtered_query & Q(proctored_exam__is_proctored=False)

        return self.filter(filtered_query).prefetch_related('proctoring_service').order_by('-created')

    def get_filtered_exam_attempts(self, course_id, search_by, timed_exams_only=False):
        """
        Returns the Student Exam Attempts for the given course_id filtered by search_by.
        """
        filtered_query = Q(proctored_exam__course_id=course_id) & (
            Q(user__username__contains=search_by) | Q(user__email__contains=search_by)
        )
        if timed_exams_only:
            filtered_query = filtered_query & Q(proctored_exam__is_proctored=False)

        return self.filter(filtered_query).prefetch_related('proctoring_service')\
            .order_by('-created')  # pylint: disable=no-member

    def get_proctored_exam_attempts(self, course_id, username):
        """
        Returns the Student's Proctored Exam Attempts for the given course_id.
        """
        return self.filter(
            proctored_exam__course_id=course_id,
            user__username=username,
            taking_as_proctored=True,
            is_sample_attempt=False,
        ).prefetch_related('proctoring_service').order_by('-completed_at')

    def get_active_student_attempts(self, user_id, course_id=None):
        """
        Returns the active student exams (user in-progress exams)
        """
        filtered_query = Q(user_id=user_id) & (Q(status=ProctoredExamStudentAttemptStatus.started) |
                                               Q(status=ProctoredExamStudentAttemptStatus.ready_to_submit))
        if course_id is not None:
            filtered_query = filtered_query & Q(proctored_exam__course_id=course_id)

        return self.filter(filtered_query).prefetch_related('proctoring_service')\
            .order_by('-created')  # pylint: disable=no-member


class ProctoredExamStudentAttempt(TimeStampedModel):
    """
    Information about the Student Attempt on a
    Proctored Exam.
    """
    objects = ProctoredExamStudentAttemptManager()

    user = models.ForeignKey(User, db_index=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # started/completed date times
    started_at = models.DateTimeField(null=True)

    # completed_at means when the attempt was 'submitted'
    completed_at = models.DateTimeField(null=True)

    # These two fields have been deprecated.
    # They were used in client polling that no longer exists.
    last_poll_timestamp = models.DateTimeField(null=True)
    last_poll_ipaddr = models.CharField(max_length=32, null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField()

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField(default=False, verbose_name=ugettext_noop("Taking as Proctored"))

    # Whether this attempt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField(default=False, verbose_name=ugettext_noop("Is Sample Attempt"))

    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

    # if student has press the button to explore the exam then true
    # else always false
    is_status_acknowledged = models.BooleanField(default=False)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempt'
        verbose_name = 'proctored exam attempt'
        unique_together = (('user', 'proctored_exam'),)

    @property
    def provider_name(self):
        try:
            return self.proctoring_service.service
        except ProctoredExamStudentAttemptProctoringService.DoesNotExist:
            return None

    @classmethod
    def create_exam_attempt(cls, exam_id, user_id, student_name, allowed_time_limit_mins,
                            attempt_code, taking_as_proctored, is_sample_attempt, external_id,
                            provider_name='',
                            review_policy_id=None):
        """
        Create a new exam attempt entry for a given exam_id and
        user_id.
        """

        exam_attempt = cls.objects.create(
            proctored_exam_id=exam_id,
            user_id=user_id,
            student_name=student_name,
            allowed_time_limit_mins=allowed_time_limit_mins,
            attempt_code=attempt_code,
            taking_as_proctored=taking_as_proctored,
            is_sample_attempt=is_sample_attempt,
            external_id=external_id,
            status=ProctoredExamStudentAttemptStatus.created,
            review_policy_id=review_policy_id
        )  # pylint: disable=no-member
        if provider_name:
            ProctoredExamStudentAttemptProctoringService(attempt=exam_attempt, service=provider_name.strip()).save()
        return exam_attempt

    def delete_exam_attempt(self):
        """
        deletes the exam attempt object and archives it to the ProctoredExamStudentAttemptHistory table.
        """
        self.delete()


class ProctoredExamStudentAttemptHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAttempt
    but will record (for audit history) all entries that have been updated.
    """

    user = models.ForeignKey(User, db_index=True)

    # this is the PK of the original table, note this is not a FK
    attempt_id = models.IntegerField(null=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # started/completed date times
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField()

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField(default=False)

    # Whether this attampt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField(default=False)

    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

    # These two fields have been deprecated.
    # They were used in client polling that no longer exists.
    last_poll_timestamp = models.DateTimeField(null=True)
    last_poll_ipaddr = models.CharField(max_length=32, null=True)

    @property
    def provider_name(self):
        try:
            return self.proctoring_service.service
        except ProctoredExamStudentAttemptHistoryProctoringService.DoesNotExist:
            return None

    @classmethod
    def get_exam_attempt_by_code(cls, attempt_code):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        # NOTE: compared to the ProctoredExamAttempt table
        # we can have multiple rows with the same attempt_code
        # So, just return the first one (most recent) if
        # there are any
        exam_attempt_obj = None

        try:
            exam_attempt_obj = cls.objects.filter(attempt_code=attempt_code).latest("created")
        except cls.DoesNotExist:  # pylint: disable=no-member
            pass

        return exam_attempt_obj

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempthistory'
        verbose_name = 'proctored exam attempt history'


@receiver(pre_delete, sender=ProctoredExamStudentAttempt)
def on_attempt_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the exam attempt when the item is about to be deleted
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAttemptHistory(
        user=instance.user,
        attempt_id=instance.id,
        proctored_exam=instance.proctored_exam,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
        attempt_code=instance.attempt_code,
        external_id=instance.external_id,
        allowed_time_limit_mins=instance.allowed_time_limit_mins,
        status=instance.status,
        taking_as_proctored=instance.taking_as_proctored,
        is_sample_attempt=instance.is_sample_attempt,
        student_name=instance.student_name,
        review_policy_id=instance.review_policy_id,
        last_poll_timestamp=instance.last_poll_timestamp,
        last_poll_ipaddr=instance.last_poll_ipaddr,
    )
    archive_object.save()
    try:
        if instance.proctoring_service.service:
            ProctoredExamStudentAttemptHistoryProctoringService(
                attempt=archive_object,
                service=instance.proctoring_service.service).save()

    except ProctoredExamStudentAttemptProctoringService.DoesNotExist:
        pass


@receiver(pre_save, sender=ProctoredExamStudentAttempt)
def on_attempt_updated(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the exam attempt whenever the attempt status is about to be
    modified. Make a new entry with the previous value of the status in the
    ProctoredExamStudentAttemptHistory table.
    """

    if instance.id:
        # on an update case, get the original
        # and see if the status has changed, if so, then we need
        # to archive it
        original = ProctoredExamStudentAttempt.objects.get(id=instance.id)

        if original.status != instance.status:
            archive_object = ProctoredExamStudentAttemptHistory(
                user=original.user,
                attempt_id=original.id,
                proctored_exam=original.proctored_exam,
                started_at=original.started_at,
                completed_at=original.completed_at,
                attempt_code=original.attempt_code,
                external_id=original.external_id,
                allowed_time_limit_mins=original.allowed_time_limit_mins,
                status=original.status,
                taking_as_proctored=original.taking_as_proctored,
                is_sample_attempt=original.is_sample_attempt,
                student_name=original.student_name,
                review_policy_id=original.review_policy_id,
                last_poll_timestamp=original.last_poll_timestamp,
                last_poll_ipaddr=original.last_poll_ipaddr,
            )
            archive_object.save()
            try:
                if original.proctoring_service.service:
                    ProctoredExamStudentAttemptHistoryProctoringService(
                        attempt=archive_object,
                        service=original.proctoring_service.service).save()

            except ProctoredExamStudentAttemptProctoringService.DoesNotExist:
                pass


class QuerySetWithUpdateOverride(models.QuerySet):
    """
    Custom QuerySet class to make an archive copy
    every time the object is updated.
    """
    def update(self, **kwargs):
        super(QuerySetWithUpdateOverride, self).update(**kwargs)
        _make_archive_copy(self.get())


class ProctoredExamStudentAllowanceManager(models.Manager):
    """
    Custom manager to override with the custom queryset
    to enable archiving on Allowance updation.
    """
    def get_queryset(self):
        """
        Return a specialized queryset
        """
        return QuerySetWithUpdateOverride(self.model, using=self._db)


class ProctoredExamStudentAllowance(TimeStampedModel):
    """
    Information about allowing a student additional time on exam.
    """

    # DONT EDIT THE KEYS - THE FIRST VALUE OF THE TUPLE - AS ARE THEY ARE STORED IN THE DATABASE
    # THE SECOND ELEMENT OF THE TUPLE IS A DISPLAY STRING AND CAN BE EDITED
    ADDITIONAL_TIME_GRANTED = ('additional_time_granted', ugettext_noop('Additional Time (minutes)'))
    REVIEW_POLICY_EXCEPTION = ('review_policy_exception', ugettext_noop('Review Policy Exception'))

    all_allowances = [
        ADDITIONAL_TIME_GRANTED + REVIEW_POLICY_EXCEPTION
    ]

    objects = ProctoredExamStudentAllowanceManager()

    user = models.ForeignKey(User)

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('user', 'proctored_exam', 'key'),)
        db_table = 'proctoring_proctoredexamstudentallowance'
        verbose_name = 'proctored allowance'

    @classmethod
    def get_allowances_for_course(cls, course_id, timed_exams_only=False):
        """
        Returns all the allowances for a course.
        """
        filtered_query = Q(proctored_exam__course_id=course_id)
        if timed_exams_only:
            filtered_query = filtered_query & Q(proctored_exam__is_proctored=False)

        return cls.objects.filter(filtered_query)

    @classmethod
    def get_allowance_for_user(cls, exam_id, user_id, key):
        """
        Returns an allowance for a user within a given exam
        """
        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
        except cls.DoesNotExist:  # pylint: disable=no-member
            student_allowance = None
        return student_allowance

    @classmethod
    def get_allowances_for_user(cls, exam_id, user_id):
        """
        Returns an allowances for a user within a given exam
        """
        return cls.objects.filter(proctored_exam_id=exam_id, user_id=user_id)

    @classmethod
    def add_allowance_for_user(cls, exam_id, user_info, key, value):
        """
        Add or (Update) an allowance for a user within a given exam
        """
        user_id = None

        # see if key is a tuple, if it is, then the first element is the key
        if isinstance(key, tuple) and len(key) > 0:
            key = key[0]

        if not cls.is_allowance_value_valid(key, value):
            err_msg = _(
                'allowance_value "{value}" should be non-negative integer value.'
            ).format(value=value)
            raise AllowanceValueNotAllowedException(err_msg)
        # were we passed a PK?
        if isinstance(user_info, (int, long)):
            user_id = user_info
        else:
            # we got a string, so try to resolve it
            users = User.objects.filter(username=user_info)
            if not users.exists():
                users = User.objects.filter(email=user_info)

            if not users.exists():
                err_msg = _(
                    'Cannot find user against {user_info}'
                ).format(user_info=user_info)
                raise UserNotFoundException(err_msg)

            user_id = users[0].id

        exam = ProctoredExam.get_exam_by_id(exam_id)
        if exam and not exam.is_active:
            raise ProctoredExamNotActiveException

        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
            student_allowance.value = value
            student_allowance.save()
            action = "updated"
        except cls.DoesNotExist:  # pylint: disable=no-member
            student_allowance = cls.objects.create(proctored_exam_id=exam_id, user_id=user_id, key=key, value=value)
            action = "created"
        return student_allowance, action

    @classmethod
    def is_allowance_value_valid(cls, allowance_type, allowance_value):
        """
        Method that validates the allowance value against the allowance type
        """
        # validates the allowance value only when the allowance type is "ADDITIONAL_TIME_GRANTED"
        if allowance_type in cls.ADDITIONAL_TIME_GRANTED:
            if not allowance_value.isdigit():
                return False

        return True

    @classmethod
    def get_additional_time_granted(cls, exam_id, user_id):
        """
        Helper method to get the additional time granted
        """
        allowance = cls.get_allowance_for_user(exam_id, user_id, cls.ADDITIONAL_TIME_GRANTED[0])
        if allowance:
            return int(allowance.value)

        return None

    @classmethod
    def get_review_policy_exception(cls, exam_id, user_id):
        """
        Helper method to get the policy exception that reviewers should
        follow
        """
        allowance = cls.get_allowance_for_user(exam_id, user_id, cls.REVIEW_POLICY_EXCEPTION[0])
        return allowance.value if allowance else None


class ProctoredExamStudentAllowanceHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAllowance
    but will record (for audit history) all entries that have been updated.
    """

    # what was the original id of the allowance
    allowance_id = models.IntegerField()

    user = models.ForeignKey(User)

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentallowancehistory'
        verbose_name = 'proctored allowance history'


# Hook up the post_save signal to record creations in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=ProctoredExamStudentAllowance)
def on_allowance_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        original = ProctoredExamStudentAllowance.objects.get(id=instance.id)
        _make_archive_copy(original)


@receiver(pre_delete, sender=ProctoredExamStudentAllowance)
def on_allowance_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_archive_copy(instance)


def _make_archive_copy(item):
    """
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAllowanceHistory(
        allowance_id=item.id,
        user=item.user,
        proctored_exam=item.proctored_exam,
        key=item.key,
        value=item.value
    )
    archive_object.save()


class ProctoredExamSoftwareSecureReview(TimeStampedModel):
    """
    This is where we store the proctored exam review feedback
    from the exam reviewers
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True, unique=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    # NOTE: To be deleted in future release, once the code that depends on it
    # has been removed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(User, null=True, related_name='+')

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(User, null=True, related_name='+')

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereview'
        verbose_name = 'Proctored exam software secure review'

    @classmethod
    def get_review_by_attempt_code(cls, attempt_code):
        """
        Does a lookup by attempt_code
        """
        try:
            review = cls.objects.get(attempt_code=attempt_code)
            return review
        except cls.DoesNotExist:  # pylint: disable=no-member
            return None


class ProctoredExamSoftwareSecureReviewHistory(TimeStampedModel):
    """
    When records get updated, we will archive them here
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(User, null=True, related_name='+')

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(User, null=True, related_name='+')

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereviewhistory'
        verbose_name = 'Proctored exam review archive'


# Hook up the post_save signal to record creations in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=ProctoredExamSoftwareSecureReview)
def on_review_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        # only for update cases
        original = ProctoredExamSoftwareSecureReview.objects.get(id=instance.id)
        _make_review_archive_copy(original)


@receiver(pre_delete, sender=ProctoredExamSoftwareSecureReview)
def on_review_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_review_archive_copy(instance)


def _make_review_archive_copy(instance):
    """
    Do the copying into the history table
    """

    archive_object = ProctoredExamSoftwareSecureReviewHistory(
        attempt_code=instance.attempt_code,
        review_status=instance.review_status,
        raw_data=instance.raw_data,
        reviewed_by=instance.reviewed_by,
        student=instance.student,
        exam=instance.exam,
    )
    archive_object.save()


class ProctoredExamSoftwareSecureComment(TimeStampedModel):
    """
    This is where we store the proctored exam review comments
    from the exam reviewers
    """

    # which student attempt is this feedback for?
    review = models.ForeignKey(ProctoredExamSoftwareSecureReview)

    # start time in the video, in seconds, regarding the comment
    start_time = models.IntegerField()

    # stop time in the video, in seconds, regarding the comment
    stop_time = models.IntegerField()

    # length of time, in seconds, regarding the comment
    duration = models.IntegerField()

    # the text that the reviewer typed in
    comment = models.TextField()

    # reviewers opinion regarding exam validitity based on the comment
    status = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattemptcomment'
        verbose_name = 'proctored exam software secure comment'


class ProctoredCourse(TimeStampedModel):
    """
    This is where we store the proctored courses
    """
    edx_id = models.CharField(max_length=255, primary_key=True)
    name = models.TextField()
    org = models.CharField(max_length=255)
    run = models.CharField(max_length=255)
    course = models.CharField(max_length=255)
    image_url = models.CharField(max_length=255, null=True, blank=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    category = "course"
    _available_proctoring_services = None

    @property
    def id(self):
        return CourseKey.from_string(self.edx_id)

    @property
    def display_name(self):
        return self.name

    @property
    def available_proctoring_services(self):
        if self._available_proctoring_services is None:
            self._available_proctoring_services = sorted([s.name for s in self.proctoring_services.all()])
        return ','.join(self._available_proctoring_services)

    @classmethod
    def fetch_all(cls):
        return cls.objects.all().prefetch_related('proctoring_services').order_by('name')

    @classmethod
    def fetch_by_course_ids(cls, course_ids):
        return cls.objects.filter(edx_id__in=course_ids).prefetch_related('proctoring_services').order_by('name')

    @classmethod
    def create_new_from_edx_course(cls, edx_course):
        proctored_course = cls(edx_id=unicode(edx_course.id))
        proctored_course.set_fields_from_edx_course(edx_course)
        proctored_course.save()
        return proctored_course

    def set_fields_from_edx_course(self, edx_course):
        course_image = course_image_url(edx_course)

        self.name = edx_course.display_name
        self.org = edx_course.id.org
        self.run = edx_course.id.run
        self.course = edx_course.id.course
        self.image_url = course_image if course_image else None
        self.start = edx_course.start if edx_course.start else None
        self.end = edx_course.end if edx_course.end else None

    class scope_ids:
        block_type = 'course'

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredcourse'
        verbose_name = 'Proctored course'


class ProctoredCourseProctoringService(TimeStampedModel):
    """
    This is where we store available proctoring services for the courses
    """
    course = models.ForeignKey(ProctoredCourse, related_name="proctoring_services")
    name = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (("course", "name"),)
        db_table = 'proctoring_proctoredcourseproctoringservice'
        verbose_name = 'Proctoring service'


class ProctoredExamParams(models.Model):
    """
    This is where we store additional params for exam (one-to-one)
    """
    exam = models.OneToOneField(ProctoredExam, primary_key=True,
                                related_name="proctored_exam_params")
    updated = models.BooleanField(default=False)  # this field is necessary only for migration
    service = models.CharField(max_length=255, null=True)
    deadline = models.DateTimeField(null=True)
    start = models.DateTimeField(null=True)
    visible_to_staff_only = models.BooleanField(default=False)
    exam_review_checkbox = JSONField(default={})

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexam_params'
        verbose_name = 'proctored exam params'


class ProctoredExamStudentAttemptProctoringService(models.Model):
    """
    This is where we store proctoring service for exam attempts (one-to-one)
    """
    attempt = models.OneToOneField(ProctoredExamStudentAttempt, primary_key=True,
                                   related_name="proctoring_service")
    service = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempt_proctoringservice'
        verbose_name = 'proctored exam attempt proctoring service'


class ProctoredExamStudentAttemptHistoryProctoringService(models.Model):
    """
    This is where we store proctoring service for exam attempts history (one-to-one)
    """
    attempt = models.OneToOneField(ProctoredExamStudentAttemptHistory, primary_key=True,
                                   related_name="proctoring_service")
    service = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempthistory_proctoringservice'
        verbose_name = 'proctored exam attempt history proctoring service'
