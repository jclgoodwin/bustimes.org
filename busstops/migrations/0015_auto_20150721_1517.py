# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0014_auto_20150712_2331'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='locality',
            name='easting',
        ),
        migrations.RemoveField(
            model_name='locality',
            name='northing',
        ),
        migrations.AddField(
            model_name='locality',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(srid=27700, null=True),
        ),
        migrations.AddField(
            model_name='stoppoint',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(srid=27700, null=True),
        ),
    ]
