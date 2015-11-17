from django.contrib import admin
from busstops.models import Region, AdminArea, District, Locality, StopArea, StopPoint, Operator, Service


admin.site.register(Region)
admin.site.register(AdminArea)
admin.site.register(District)
admin.site.register(Locality)
admin.site.register(StopArea)
admin.site.register(StopPoint)
admin.site.register(Operator)
admin.site.register(Service)
