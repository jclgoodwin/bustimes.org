
import os
import zipfile
from txc import txc


DIR = os.path.dirname(__file__)


def get_filenames(service, path=None, archive=None):
    suffix = '' if archive is None else '.xml'

    if service.region_id == 'NE':
        return ['%s%s' % (service.pk, suffix)]
    if service.region_id in ('S', 'NW'):
        return ['SVR%s%s' % (service.pk, suffix)]

    try:
        if archive is None:
            namelist = os.listdir(path)
        else:
            namelist = archive.namelist()
    except OSError:
        return []

    if service.net:
        return [name for name in namelist if name.startswith('%s-' % service.pk)]
    if service.region_id == 'GB':
        parts = service.pk.split('_')
        return [name for name in namelist if name.endswith('_%s_%s%s' % (parts[1], parts[0], suffix))]
    if service.region_id == 'Y':
        return [
            name for name in namelist
            if name.startswith('SVR%s-' % service.pk) or name == 'SVR%s%s' % (service.pk, suffix)
        ]
    return [name for name in namelist if name.endswith('_%s%s' % (service.pk, suffix))]


def get_pickle_filenames(service, path):
    """Given a Service and a folder path, return a list of filenames."""
    return get_filenames(service, path)


def get_files_from_zipfile(service):
    """Given a Service,
    return an iterable of open files from the relevant zipfile.
    """
    service_code = service.service_code
    if service.region_id == 'GB':
        archive_name = 'NCSD'
        parts = service_code.split('_')
        service_code = '_%s_%s' % (parts[-1], parts[-2])
    else:
        archive_name = service.region_id

    archive_path = os.path.join(DIR, '../data/TNDS/', archive_name + '.zip')
    with zipfile.ZipFile(archive_path) as archive:
        filenames = get_filenames(service, archive=archive)
        return [archive.open(filename) for filename in filenames]


def timetable_from_service(service):
    """Given a Service, return a list of Timetables."""
    if service.region_id == 'GB':
        path = os.path.join(DIR, '../data/TNDS/NCSD/NCSD_TXC/')
    else:
        path = os.path.join(DIR, '../data/TNDS/%s/' % service.region_id)

    filenames = get_pickle_filenames(service, path)
    if filenames:
        maybe_timetables = (txc.timetable_from_filename(path, name) for name in filenames)
        timetables = [timetable for timetable in maybe_timetables if timetable]
        if timetables:
            return timetables
    return [txc.Timetable(xml_file) for xml_file in get_files_from_zipfile(service)]
