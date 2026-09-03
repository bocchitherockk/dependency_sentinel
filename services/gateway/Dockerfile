FROM python:3.12-slim

RUN pip install uv
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml uv.lock ./
# Copier les librairies partagees
COPY libs/ libs/
# Copier uniquement le code de ce service
COPY services/gateway/ services/gateway/

# Installer uniquement les dependances necessaires a ce service
RUN uv sync --package gateway

ENTRYPOINT ["uv", "run", "--package", "gateway", "gateway"]
