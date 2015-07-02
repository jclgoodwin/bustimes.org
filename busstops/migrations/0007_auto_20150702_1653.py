# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0006_auto_20150702_1547'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='service_code',
            field=models.CharField(max_length=24, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='serviceversion',
            name='service',
            field=models.ForeignKey(editable=False, to='busstops.Service'),
        ),
    ]
