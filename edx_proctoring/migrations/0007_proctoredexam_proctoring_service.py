# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0006_provider_name_field_in_exam_attempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='proctoredexam',
            name='proctoring_service',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
