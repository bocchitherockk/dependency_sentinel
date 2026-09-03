FROM python:3.12-slim

RUN pip install uv
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml uv.lock ./
# Copier les librairies partagees
COPY libs/ libs/
# Copier uniquement le code de ce service
COPY services/security_intelligence_service/ services/security_intelligence_service/

# Installer uniquement les dependances necessaires a ce service
RUN uv sync --package security-intelligence-service

ENTRYPOINT ["uv", "run", "--package", "security-intelligence-service", "security-intelligence-service"]
