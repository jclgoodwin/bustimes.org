FROM node:current

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

COPY busstops/static /app/busstops/static
COPY Makefile /app/
RUN make build-static


FROM python:3.11.0rc2

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y gdal-bin && rm -rf /var/lib/apt/lists/*

ENV POETRY_HOME=/opt/poetry
RUN python -m venv $POETRY_HOME
RUN $POETRY_HOME/bin/pip install poetry==1.2.2
ENV PATH=$POETRY_HOME/bin:$PATH

WORKDIR /app/

COPY poetry.lock pyproject.toml /app/
RUN poetry install --no-dev

COPY . /app/
COPY --from=0 /app/busstops/static /app/busstops/static
COPY --from=0 /app/node_modules /app/node_modules

ENV SECRET_KEY=f
ENV STATIC_ROOT=/app/staticfiles
RUN poetry run ./manage.py collectstatic --noinput

CMD ["poetry", "run", "gunicorn", "buses.wsgi"]
