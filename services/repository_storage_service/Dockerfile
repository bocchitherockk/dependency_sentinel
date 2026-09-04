FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git config --global user.name "Yassine"
RUN git config --global user.email "yassinemakhlouf5@gmail.com"

RUN pip install uv
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml .
COPY .python-version .
COPY README.md .
COPY .env .

ARG DIR_NAME="repository_storage_service"
ARG SERVICE_NAME="repository-storage-service"
ENV SERVICE_NAME=${SERVICE_NAME}

COPY libs/ libs/
COPY services/${DIR_NAME}/ services/${DIR_NAME}/

RUN uv sync --all-packages

ENTRYPOINT ["sh", "-c", "uv run ${SERVICE_NAME}"]
