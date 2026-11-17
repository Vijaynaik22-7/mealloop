# Base image: small official Python 3.11
FROM python:3.11-slim

# Don't write .pyc files, and print logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first so Docker caches the install layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create a non-root user and give it the folder for the SQLite database
RUN useradd --create-home appuser \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Docker marks the container "healthy" if /health answers
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# --preload imports the app once, so db.create_all() runs once (no two-worker race).
# One worker is enough for SQLite and a demo.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--preload", "run:app"]