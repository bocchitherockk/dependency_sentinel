FROM python:3.12-slim

RUN pip install uv
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copier la configuration globale du workspace
COPY pyproject.toml .
COPY .python-version .
COPY README.md .
COPY .env .

ARG DIR_NAME="mcp_server"
ARG SERVICE_NAME="mcp-server"
ENV SERVICE_NAME=${SERVICE_NAME}

COPY libs/ libs/
COPY services/${DIR_NAME}/ services/${DIR_NAME}/

RUN uv sync --all-packages

ENTRYPOINT ["sh", "-c", "uv run ${SERVICE_NAME}"]
