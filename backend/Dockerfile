FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Playwright deps
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user BEFORE installing Playwright
RUN useradd -m -u 1000 appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /home/appuser

# Install Playwright browsers as appuser
USER appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright
RUN playwright install chromium

# Switch back to root for copying files
USER root

# Copy application code
COPY . .
RUN chown -R appuser:appuser /app

# Switch to appuser for running
USER appuser

# Expose port
EXPOSE 8000

# Run migrations and start application
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
