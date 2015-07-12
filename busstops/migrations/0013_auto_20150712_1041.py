# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0012_locality_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='StopArea',
            fields=[
                ('id', models.CharField(max_length=16, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=48)),
                ('stop_area_type', models.CharField(max_length=4, choices=[(b'GPBS', b'on-street pair'), (b'GCLS', b'on-street cluster'), (b'GAIR', b'airport building'), (b'GBCS', b'bus/coach station'), (b'GFTD', b'ferry terminal/dock'), (b'GTMU', b'tram/metro station'), (b'GRLS', b'rail station')])),
                ('location', django.contrib.gis.db.models.fields.PointField(srid=27700)),
                ('active', models.BooleanField()),
                ('admin_area', models.ForeignKey(to='busstops.AdminArea')),
                ('parent', models.ForeignKey(to='busstops.StopArea', null=True)),
            ],
        ),
        migrations.AddField(
            model_name='stoppoint',
            name='stop_area',
            field=models.ForeignKey(to='busstops.StopArea', null=True),
        ),
    ]
