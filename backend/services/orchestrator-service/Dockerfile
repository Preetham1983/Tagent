FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install orchestrator-service
COPY orchestrator-service/pyproject.toml ./
COPY orchestrator-service/src ./src
COPY orchestrator-service/main.py ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Pre-install Playwright and its heavy browsers so Docker caches it (won't re-download on code changes)
RUN pip install --no-cache-dir playwright>=1.40.0 \
    && playwright install --with-deps chromium

# Bundle mcp-tools-service so the orchestrator can spawn it as a subprocess
COPY mcp-tools-service /app/mcp_tools
RUN pip install --no-cache-dir /app/mcp_tools


EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
