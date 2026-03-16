from django.contrib import admin
from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    raw_id_fields = ["vehicles", "livery", "vehicle_type", "service"]
