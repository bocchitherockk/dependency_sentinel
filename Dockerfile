FROM python:3.12-slim

# Installer git (requis par repository-storage-service)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Installer uv
RUN pip install uv

# Configurer l'environnement
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copier le code source de l'application
COPY . .

# Installer toutes les dépendances via uv pour tous les packages du workspace
RUN uv sync --all-packages

# L'entrypoint permet de lancer `uv run --package <service> <service>` dynamiquement
ENTRYPOINT ["uv", "run", "--package"]
