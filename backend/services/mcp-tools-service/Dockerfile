FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY main.py ./

# Copy the note-taker avatar used as a fake camera feed by Playwright
COPY src/tagent/mcp/tools/notetaker_avatar.y4m ./src/tagent/mcp/tools/notetaker_avatar.y4m

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

CMD ["python", "main.py"]
