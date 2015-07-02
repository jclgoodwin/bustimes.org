# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AdminArea',
            fields=[
                ('id', models.PositiveIntegerField(serialize=False, primary_key=True)),
                ('atco_code', models.PositiveIntegerField()),
                ('name', models.CharField(max_length=48)),
                ('short_name', models.CharField(max_length=48)),
                ('country', models.CharField(max_length=3)),
            ],
        ),
        migrations.CreateModel(
            name='District',
            fields=[
                ('id', models.PositiveIntegerField(serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=48)),
                ('admin_area', models.ForeignKey(to='busstops.AdminArea')),
            ],
        ),
        migrations.CreateModel(
            name='Locality',
            fields=[
                ('id', models.CharField(max_length=48, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=48)),
                ('qualifier_name', models.CharField(max_length=48, blank=True)),
                ('easting', models.PositiveIntegerField()),
                ('northing', models.PositiveIntegerField()),
                ('admin_area', models.ForeignKey(to='busstops.AdminArea')),
                ('district', models.ForeignKey(to='busstops.District', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.CharField(max_length=2, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=48)),
            ],
        ),
        migrations.CreateModel(
            name='StopPoint',
            fields=[
                ('atco_code', models.CharField(max_length=16, serialize=False, primary_key=True)),
                ('naptan_code', models.CharField(max_length=16)),
                ('common_name', models.CharField(max_length=48)),
                ('landmark', models.CharField(max_length=48)),
                ('street', models.CharField(max_length=48)),
                ('crossing', models.CharField(max_length=48)),
                ('indicator', models.CharField(max_length=48)),
                ('latlong', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('suburb', models.CharField(max_length=48)),
                ('town', models.CharField(max_length=48)),
                ('locality_centre', models.BooleanField()),
                ('bearing', models.CharField(max_length=2, choices=[(b'N', b'north'), (b'NE', b'north east'), (b'E', b'east'), (b'SE', b'south east'), (b'S', b'south'), (b'SW', b'south west'), (b'W', b'west'), (b'NW', b'north west')])),
                ('stop_type', models.CharField(max_length=3)),
                ('bus_stop_type', models.CharField(max_length=3)),
                ('timing_status', models.CharField(max_length=3)),
                ('active', models.BooleanField()),
                ('admin_area', models.ForeignKey(to='busstops.AdminArea')),
                ('locality', models.ForeignKey(editable=False, to='busstops.Locality')),
            ],
        ),
        migrations.AddField(
            model_name='adminarea',
            name='region',
            field=models.ForeignKey(to='busstops.Region'),
        ),
    ]
