from huey.contrib.djhuey import task

from . import countdown


@task()
def refresh_countdown():
    countdown.refresh()
