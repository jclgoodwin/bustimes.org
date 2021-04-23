FROM python:3.9-buster

RUN apt-get update && apt-get install -y gdal-bin

RUN pip install pipenv

WORKDIR /app/
COPY Pipfile* /app/
RUN pipenv sync --dev

COPY . /app/

ENV STATICFILES_DIR=/staticfiles/
RUN pipenv run ./manage.py collectstatic

ENV PGHOST=host.docker.internal
ENV PGUSER=josh
ENV DEBUG=1
ENV SECRET_KEY=wenceslas
CMD pipenv run ./manage.py runserver 0.0.0.0:8000
