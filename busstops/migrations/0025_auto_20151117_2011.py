# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0024_service_current'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='serviceversion',
            name='service',
        ),
        migrations.DeleteModel(
            name='ServiceVersion',
        ),
    ]
