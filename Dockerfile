FROM python:3.9-buster

RUN apt-get update && apt-get install -y gdal-bin

RUN pip install poetry

WORKDIR /app/
COPY poetry.lock pyproject.toml /app/
RUN poetry install
