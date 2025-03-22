FROM node:20-slim

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

COPY frontend /app/frontend
COPY tsconfig.json /app/
RUN npm run lint && npm run build


FROM python:3.13

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=off PIP_DISABLE_PIP_VERSION_CHECK=on

# install GDAL (https://docs.djangoproject.com/en/5.1/ref/contrib/gis/install/geolibs/)
RUN apt-get update && \
    apt-get install -y --no-install-recommends binutils libproj-dev gdal-bin && \
    rm -rf /var/lib/apt && \
    rm -rf /var/lib/dpkg/info/*

ENV VIRTUAL_ENV=/opt/poetry
RUN python -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN $VIRTUAL_ENV/bin/pip install poetry==2.0.0

WORKDIR /app/

COPY poetry.lock pyproject.toml /app/
RUN poetry install --only main

COPY --from=0 /app/node_modules/htmx.org/dist /app/node_modules/htmx.org/dist
COPY --from=0 /app/node_modules/reqwest/reqwest.min.js /app/node_modules/reqwest/
COPY --from=0 /app/busstops/static /app/busstops/static
COPY . /app/

ENV PORT=8000 STATIC_ROOT=/staticfiles
RUN SECRET_KEY= ./manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["gunicorn", "buses.wsgi"]
