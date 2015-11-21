# Bus Times

## What's this?

It's [a thing about buses](https://bustimes.org.uk/).

## Installing

A database supported by GeoDjango is required – I use PostgreSQL with PostGIS.
I also use Nginx and uwsgi in production.

Here I've noted down some of the commands I used when manually provisioning a new server:

    apt-get install postgresql postgresql-contrib
    apt-get install libpq-dev python-dev gcc
    apt-get install python-virtualenv
    virtualenv env
    . env/bin/activate
    pip install django django-pipeline psycopg2
    apt-get install binutils libproj-dev gdal-bin
    apt-get install postgis
    apt-get install nginx uwsgi uwsgi-plugin-python

## Importing data

[NPTG][nptg] data should be imported in this order:

    ./manage.py import_regions < Regions.csv
    ./manage.py import_areas < AdminAreas.csv
    ./manage.py import_districts < Districts.csv
    ./manage.py import_localities < Localities.csv
    ./manage.py import_locality_hierarchy < LocalityHierarchy.csv

 Then [NaPTAN][naptan] data (the order is less important, as long as StopsInArea is imported last):

    ./manage.py import_stop_areas < StopAreas.csv
    ./manage.py import_stops < Stops.csv
    ./manage.py import_stops_in_area < StopsInArea.csv

Then NOC (bus operators) and TNDS (bus services) data can be imported,
which is slightly more complicated and needs work.

[nptg]: http://data.gov.uk/dataset/nptg
[naptan]: http://data.gov.uk/dataset/naptan
