FROM python:3.9-buster

RUN apt-get update && apt-get install -y gdal-bin

RUN pip install pipenv

WORKDIR /app/
COPY Pipfile* /app/
RUN pipenv sync --dev

COPY . /app/

ENV PGHOST=host.docker.internal:8000

CMD ['pipenv run ./manage.py runserver']
