# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=9000

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY . /app/demo/store/
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 9000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/store/products || exit 1

CMD ["sh", "-c", "uvicorn demo.store.main:app --host 0.0.0.0 --port ${PORT}"]
