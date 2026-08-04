FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analyzer/ ./analyzer/
COPY app.py .
COPY paper_trading_service.py .
COPY mcp_stock_agent.py .
COPY notification_manager.py .
COPY sp500_tickers_500.py .
COPY sp500_full_tickers.py .
COPY config.py .
COPY config.yaml .
COPY logger.py .
COPY helpers.py .
COPY validators.py .

# Verify all imports resolve at build time
RUN python -c "import app" && echo "Import check passed"

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
