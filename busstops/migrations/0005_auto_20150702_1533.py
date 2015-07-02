# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0004_service_serviceversion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serviceversion',
            name='name',
            field=models.CharField(max_length=24, serialize=False, primary_key=True),
        ),
    ]
