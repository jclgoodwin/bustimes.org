# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0011_auto_20150707_0232'),
    ]

    operations = [
        migrations.AddField(
            model_name='locality',
            name='parent',
            field=models.ForeignKey(to='busstops.Locality', null=True),
        ),
    ]
