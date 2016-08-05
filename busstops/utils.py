
import os
import zipfile
import xml.etree.cElementTree as ET
from txc import txc


DIR = os.path.dirname(__file__)


def get_pickle_filenames(service, path):
    """Given a Service and a folder path, return a list of filenames."""
    if service.region_id == 'NE':
        return [service.pk]
    if service.region_id in ('S', 'NW'):
        return ['SVR%s' % service.pk]
    try:
        namelist = os.listdir(path)
    except OSError:
        return []
    if service.net:
        return [name for name in namelist if name.startswith('%s-' % service.pk)]
    if service.region_id == 'GB':
        parts = service.pk.split('_')
        return [name for name in namelist if name.endswith('_%s_%s' % (parts[1], parts[0]))]
    if service.region_id == 'Y':
        return [
            name for name in namelist
            if name.startswith('SVR%s-' % service.pk) or name == 'SVR%s' % service.pk
        ]
    return [name for name in namelist if name.endswith('_%s' % service.pk)]


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
    archive = zipfile.ZipFile(archive_path)
    filenames = (name for name in archive.namelist() if service_code in name)

    return (archive.open(filename) for filename in filenames)


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
    return [txc.Timetable(ET.parse(xml_file)) for xml_file in get_files_from_zipfile(service)]
