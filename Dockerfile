# One image runs either the API (default) or the dashboard (see docker-compose.yml).
FROM python:3.11-slim

# Don't write .pyc files; show print() output in logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTOPILOT_DB=/data/autopilot.db

WORKDIR /app

# Install dependencies first, so rebuilding after a code change can reuse this step
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a regular user rather than root, a standard security practice
RUN useradd --create-home appuser && mkdir -p /data && chown -R appuser /app /data
USER appuser

EXPOSE 8000 8501

# Hosting platforms like Render set $PORT; otherwise it defaults to 8000
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]