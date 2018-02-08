# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields
from xmodule.modulestore.django import modulestore
from openedx.core.lib.courses import course_image_url


def migrate_all_courses(apps, schema_editor):
    ProctoredCourse = apps.get_model("edx_proctoring", "ProctoredCourse")
    ProctoredCourseProctoringService = apps.get_model("edx_proctoring", "ProctoredCourseProctoringService")

    courses = modulestore().get_courses()
    for course in courses:
        services_list_to_save = [service.strip() for service in course.available_proctoring_services.split(',')
                                 if service.strip()]
        services_list_to_save = list(set(services_list_to_save))
        if services_list_to_save:
            course_image = course_image_url(course)

            proctored_course = ProctoredCourse(
                edx_id=unicode(course.id),
                name=course.display_name,
                org=course.id.org,
                run=course.id.run,
                course=course.id.course,
                image_url=course_image if course_image else None,
                start=course.start if course.start else None,
                end=course.end if course.end else None
            )
            proctored_course.save()
            for service_name in services_list_to_save:
                new_service = ProctoredCourseProctoringService(
                    course=proctored_course,
                    name=service_name)
                new_service.save()


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0007_proctoredexam_proctoring_service'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProctoredCourse',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('edx_id', models.CharField(max_length=255, serialize=False, primary_key=True)),
                ('name', models.TextField()),
                ('org', models.CharField(max_length=255)),
                ('run', models.CharField(max_length=255)),
                ('course', models.CharField(max_length=255)),
                ('image_url', models.CharField(max_length=255, null=True, blank=True)),
                ('start', models.DateTimeField(null=True)),
                ('end', models.DateTimeField(null=True)),
            ],
            options={
                'db_table': 'proctoring_proctoredcourse',
                'verbose_name': 'Proctored course',
            },
        ),
        migrations.CreateModel(
            name='ProctoredCourseProctoringService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('name', models.CharField(max_length=255)),
                ('course', models.ForeignKey(related_name='proctoring_services', to='edx_proctoring.ProctoredCourse')),
            ],
            options={
                'db_table': 'proctoring_proctoredcourseproctoringservice',
                'verbose_name': 'Proctoring service',
            },
        ),
        migrations.AlterUniqueTogether(
            name='proctoredcourseproctoringservice',
            unique_together=set([('course', 'name')]),
        ),
        migrations.RunPython(
            migrate_all_courses,
        ),
    ]
