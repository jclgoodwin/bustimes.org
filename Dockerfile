FROM node:current

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

COPY busstops/static /app/busstops/static
COPY Makefile /app/
RUN make build-static


FROM python:3.11-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV POETRY_HOME=/opt/poetry
RUN python -m venv $POETRY_HOME
RUN $POETRY_HOME/bin/pip install poetry==1.2.2
ENV PATH=$POETRY_HOME/bin:$PATH

WORKDIR /app/

COPY poetry.lock pyproject.toml /app/
RUN poetry install --only main


FROM python:3.11-slim-bullseye

RUN apt-get update && \
    apt-get install -y --no-install-recommends gdal-bin && \
    apt clean && \
    rm -rf /var/lib/apt && \
    rm -rf /var/lib/dpkg/info/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_HOME=/opt/poetry
ENV PATH=$POETRY_HOME/bin:$PATH

WORKDIR /app/

COPY . /app/
COPY --from=0 /app/busstops/static /app/busstops/static
COPY --from=0 /app/node_modules /app/node_modules
COPY --from=1 $POETRY_HOME $POETRY_HOME

ENV SECRET_KEY=f
ENV STATIC_ROOT=/staticfiles
RUN . /opt/poetry/bin/activate
#RUN ./manage.py collectstatic --noinput

#CMD ["gunicorn", "buses.wsgi"]
