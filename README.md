# Bus Times

## What's this?

It's [a thing about buses](https://bustimes.org.uk/).

## Dependencies

Python, Django ... there will be a `requirements.txt` soon.

A database supported by GeoDjango is required.
I use SQLite with Spatialite in development, and PostgreSQL with PostGIS in production.

I also use Nginx, uwsgi and Varnish in production.

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
