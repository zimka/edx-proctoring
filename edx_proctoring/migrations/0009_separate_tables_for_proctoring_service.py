# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0008_proctoring_proctoredcourse'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProctoredExamParams',
            fields=[
                ('exam', models.OneToOneField(related_name='proctored_exam_params', primary_key=True, serialize=False, to='edx_proctoring.ProctoredExam')),
                ('updated', models.BooleanField(default=False)),
                ('service', models.CharField(max_length=255, null=True)),
                ('deadline', models.DateTimeField(null=True)),
                ('start', models.DateTimeField(null=True)),
                ('visible_to_staff_only', models.BooleanField(default=False)),
                ('exam_review_checkbox', jsonfield.fields.JSONField(default={})),
            ],
            options={
                'db_table': 'proctoring_proctoredexam_params',
                'verbose_name': 'proctored exam params',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAttemptHistoryProctoringService',
            fields=[
                ('attempt', models.OneToOneField(related_name='proctoring_service', primary_key=True, serialize=False, to='edx_proctoring.ProctoredExamStudentAttemptHistory')),
                ('service', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattempthistory_proctoringservice',
                'verbose_name': 'proctored exam attempt history proctoring service',
            },
        ),
        migrations.CreateModel(
            name='ProctoredExamStudentAttemptProctoringService',
            fields=[
                ('attempt', models.OneToOneField(related_name='proctoring_service', primary_key=True, serialize=False, to='edx_proctoring.ProctoredExamStudentAttempt')),
                ('service', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattempt_proctoringservice',
                'verbose_name': 'proctored exam attempt proctoring service',
            },
        ),
        migrations.RunSQL("INSERT INTO proctoring_proctoredexam_params(exam_id, service, exam_review_checkbox) "
                          "SELECT id, TRIM(proctoring_service), '{}' FROM proctoring_proctoredexam "
                          "WHERE proctoring_service IS NOT NULL;"),
        migrations.RunSQL("INSERT INTO proctoring_proctoredexamstudentattempt_proctoringservice(attempt_id, service) "
                          "SELECT id, TRIM(provider_name) FROM proctoring_proctoredexamstudentattempt "
                          "WHERE provider_name IS NOT NULL;"),
        migrations.RunSQL("INSERT INTO proctoring_proctoredexamstudentattempthistory_proctoringservice "
                          "(attempt_id, service) "
                          "SELECT id, TRIM(provider_name) FROM proctoring_proctoredexamstudentattempthistory "
                          "WHERE provider_name IS NOT NULL;"),
        migrations.RemoveField(
            model_name='proctoredexam',
            name='proctoring_service',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempt',
            name='provider_name',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempthistory',
            name='provider_name',
        ),
    ]
