import csv
from busstops.models import Region, AdminArea, District


with open('Regions.csv', 'r') as csv_file:
    csv_data = csv.reader(csv_file)
    csv_data.next() # skip title
    for row in csv_data:
        region = Region(
            id=row[0],
            name=row[1],
            )
        region.save()
        print region

with open('AdminAreas.csv', 'r') as csv_file:
    csv_data = csv.reader(csv_file)
    csv_data.next() # skip title
    for row in csv_data:
        area = AdminArea(
            id=row[0],
            atco_code=row[1],
            name=row[2],
            short_name=row[4],
            country=row[6],
            region=Region.objects.get(id=row[7]),
            )
        print area
        area.save()

with open('Districts.csv', 'r') as csv_file:
    csv_data = csv.reader(csv_file)
    csv_data.next() # skip title
    for row in csv_data:
        district = District(
            id=row[0],
            name=row[1],
            admin_area=AdminArea.objects.get(id=row[3]),
            )
        print district
        district.save()

