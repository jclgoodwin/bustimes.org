FROM node:20

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

COPY busstops/static /app/busstops/static
COPY .eslintrc.js tsconfig.json /app/
RUN npm run lint && npm run build


FROM python:3.11
# the non-slim image has GCC which is needed for installing some stuff

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/opt/poetry
RUN python -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN $VIRTUAL_ENV/bin/pip install poetry==1.7.1

WORKDIR /app/

COPY poetry.lock pyproject.toml /app/
RUN poetry install --only main --no-root


FROM python:3.11-slim

# install GDAL (https://docs.djangoproject.com/en/4.1/ref/contrib/gis/install/geolibs/)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gdal-bin libxslt1.1 && \
    rm -rf /var/lib/apt && \
    rm -rf /var/lib/dpkg/info/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/poetry
ENV PATH=$VIRTUAL_ENV/bin:$PATH

WORKDIR /app/

COPY --from=1 $VIRTUAL_ENV $VIRTUAL_ENV
COPY --from=0 /app/node_modules /app/node_modules
COPY --from=0 /app/busstops/static /app/busstops/static
COPY . /app/

ENV PORT=8000 SECRET_KEY=f STATIC_ROOT=/staticfiles
RUN ./manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "buses.wsgi"]
