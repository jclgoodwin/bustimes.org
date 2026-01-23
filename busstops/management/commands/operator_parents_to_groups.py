from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.text import slugify

from busstops.models import Operator, OperatorGroup


class Command(BaseCommand):
    help = "Create OperatorGroups from Operator.parent field values"

    def handle(self, *args, **options):
        # Get all unique non-empty parent values
        parent_values = (
            Operator.objects.filter(~Q(parent=""))
            .values_list("parent", flat=True)
            .distinct()
        )

        for parent_name in parent_values:
            slug = slugify(parent_name)

            group, created = OperatorGroup.objects.get_or_create(
                slug=slug,
                defaults={"name": parent_name},
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group.name}"))
            else:
                self.stdout.write(f"Group already exists: {group.name}")

            # Link all operators with this parent to the group
            updated = Operator.objects.filter(
                parent=parent_name, group__isnull=True
            ).update(group=group)

            if updated:
                self.stdout.write(f"  Linked {updated} operator(s) to {group.name}")
