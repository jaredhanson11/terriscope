# syntax=docker/dockerfile:1

## This dockerfile sets will build any of the required backend images. The potentional images are:
## api: production api
## api-debug: debugger api
## migrations: production migrations
## migrations-local: migrations with dev dependencies for creating revisions

##  api-debug, tests, migrations, migrations-local.
ARG POETRY_VERSION=1.8

FROM alpine/git AS version
WORKDIR /git
COPY .git .git
RUN git log -1 --no-color '--pretty=Commit: %H%nDate: %cD' > git-version.txt


FROM python:3.12-slim AS base

ARG POETRY_VERSION

# Required packages to build psycopg2
RUN apt-get update && \
    apt-get install -y libpq-dev gcc

# Install poetry
RUN pip install "poetry==$POETRY_VERSION"

# Copy only requirements to cache them in docker layer
WORKDIR /app
COPY --from=version /git/git-version.txt /app/git-version.txt
COPY api/poetry.lock api/poetry.toml api/pyproject.toml /app/

# Project initialization:
RUN poetry install --no-interaction --no-ansi --no-root --only=main

#### Main API image ####
FROM python:3.12-slim AS api

# Required packages to run psycopg2
RUN apt-get update && \
    apt-get install -y libpq-dev && \
    rm -rf /var/lib/apt/list/*

WORKDIR /app

# Copy Python code to the Docker image
COPY --from=base /app/ /app/
COPY api/src /app/src
# Exclude migrations from all images except migrations and migrations-local
RUN rm -rf /app/src/migrations

EXPOSE 8000

ENTRYPOINT ["/app/.venv/bin/fastapi", "run", "src", "--port=8000", "--host=0.0.0.0"]


### Extra dependencies image ###
FROM api AS api-extra-deps
ARG POETRY_VERSION
RUN pip install "poetry==$POETRY_VERSION"
COPY api/poetry.lock api/poetry.toml api/pyproject.toml /app/


### API debug image ###
FROM api-extra-deps AS api-debug
RUN poetry install --no-interaction --no-ansi --no-root --only=debugger
EXPOSE 5678
ENTRYPOINT [ "/app/.venv/bin/python" ]
CMD [ \
    "-m", \
    "debugpy", \
    "--listen", "0.0.0.0:5678", \
    "/app/.venv/bin/fastapi", \
    "run", \
    "src", \
    "--host=0.0.0.0", \
    "--port=8000", \
    "--reload" \
    ]


### Migrations image ###
FROM api-extra-deps AS migrations
COPY api/src/migrations /app/src/migrations
RUN poetry install --no-interaction --no-ansi --no-root --only=migrations
ENV ALEMBIC_CONFIG=/app/src/migrations/alembic.ini
ENTRYPOINT [ "/app/.venv/bin/alembic" ]
CMD [ "upgrade", "head" ]


### Migrations local development image ###
FROM migrations AS migrations-local
RUN poetry install --no-interaction --no-ansi --no-root --only=dev
