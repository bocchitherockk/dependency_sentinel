FROM python:3.12-slim

RUN pip install uv
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml uv.lock ./
# Copier les librairies partagees
COPY libs/ libs/
# Copier uniquement le code de ce service
COPY services/mcp-server/ services/mcp-server/

# Installer uniquement les dependances necessaires a ce service
RUN uv sync --package mcp-server

ENTRYPOINT ["uv", "run", "--package", "mcp-server", "mcp-server"]
