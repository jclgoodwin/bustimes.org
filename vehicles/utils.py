from .models import VehicleEdit, VehicleRevision


def get_vehicle_edit(vehicle, fields, now, username):
    edit = VehicleEdit(vehicle=vehicle, datetime=now, username=username)

    for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')

    changes = {}
    if 'depot' in fields:
        changes['Depot'] = fields['depot']
    if 'previous_reg' in fields:
        changes['Previous reg'] = fields['previous_reg'].upper()
    if changes:
        edit.changes = changes

    edit.url = fields.get('url', '')

    if fields.get('colours'):
        if fields['colours'].isdigit():
            edit.livery_id = fields['colours']
        elif fields['colours']:
            edit.colours = fields['colours']
    if fields.get('other_colour'):
        edit.colours = fields['other_colour']

    edit.withdrawn = fields.get('withdrawn')

    return edit


def do_revision(vehicle, data):
    if 'operator' in data or 'reg' in data or 'depot' in data:
        revision = VehicleRevision(
            vehicle=vehicle
        )
        changed_fields = ['operator']

        if 'operator' in data:
            revision.from_operator = vehicle.operator
            revision.to_operator = data['operator']
            vehicle.operator = data['operator']
            changed_fields.append('operator')
            del data['operator']

        changes = {}

        if 'reg' in data:
            changes['reg'] = f"-{vehicle.reg}\n+{data['reg']}"
            vehicle.reg = data['reg']
            changed_fields.append('reg')
            del data['reg']

        if 'depot' in data:
            if vehicle.data:
                depot = vehicle.data.get('Depot') or ''
                vehicle.data['Depot'] = depot
            else:
                depot = ''
                vehicle.data = {'Depot': data['depot']}
            changes['depot'] = f"-{depot}\n+{data['depot']}"
            changed_fields.append('data')
            del data['depot']

        vehicle.save(update_fields=changed_fields)

        if changes:
            revision.changes = changes

        return revision
