FROM node:current

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

COPY busstops/static /app/busstops/static
COPY Makefile /app/
RUN make build-static


FROM python:3.11-bullseye
# the non-slim image has GCC which is needed for installing some stuff

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/opt/poetry
RUN python -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN $VIRTUAL_ENV/bin/pip install poetry==1.2.2

WORKDIR /app/

COPY poetry.lock pyproject.toml /app/
RUN poetry install --only main


FROM python:3.11-slim-bullseye

# install GDAL (https://docs.djangoproject.com/en/4.1/ref/contrib/gis/install/geolibs/)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gdal-bin && \
    apt clean && \
    rm -rf /var/lib/apt && \
    rm -rf /var/lib/dpkg/info/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/opt/poetry
ENV PATH=$VIRTUAL_ENV/bin:$PATH

WORKDIR /app/

COPY . /app/
COPY --from=0 /app/busstops/static /app/busstops/static
COPY --from=0 /app/node_modules /app/node_modules
COPY --from=1 $VIRTUAL_ENV $VIRTUAL_ENV

ENV SECRET_KEY=f \
    STATIC_ROOT=/staticfiles
RUN ./manage.py collectstatic --noinput

CMD ["gunicorn", "buses.wsgi"]
