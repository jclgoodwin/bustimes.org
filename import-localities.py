import csv
from busstops.models import Locality, District, AdminArea
from django.core.exceptions import ObjectDoesNotExist

with open('Localities.csv', 'r') as csv_file:
    csv_data = csv.reader(csv_file)
    csv_data.next() # skip title
    for row in csv_data:
        locality = Locality(
            id=row[0],
            name=row[1],
            qualifier_name=row[5],
            admin_area=AdminArea.objects.get(id=row[9]),
            easting=row[13],
            northing=row[14],
            )
        try:
            district = District.objects.get(id=row[10])
            locality.district = district
        except ObjectDoesNotExist:
            pass
        locality.save()
