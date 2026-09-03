FROM python:3.12-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install uv
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml uv.lock ./
# Copier les librairies partagees
COPY libs/ libs/
# Copier uniquement le code de ce service
COPY services/repository_storage_service/ services/repository_storage_service/

# Installer uniquement les dependances necessaires a ce service
RUN uv sync --package repository-storage-service

ENTRYPOINT ["uv", "run", "--package", "repository-storage-service", "repository-storage-service"]
