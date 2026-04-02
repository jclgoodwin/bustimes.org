from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from . import siri_sx, tfl_disruptions

bods_disruptions = db_periodic_task(crontab(minute="*/6"))(siri_sx.bods_disruptions)
tfl_disruptions_task = db_periodic_task(crontab(minute="*/6"))(
    tfl_disruptions.tfl_disruptions
)
