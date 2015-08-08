# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0019_auto_20150728_1442'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='net',
            field=models.CharField(max_length=3, blank=True),
        ),
    ]
