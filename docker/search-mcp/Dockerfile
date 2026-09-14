FROM python:3.11-slim

WORKDIR /app

# Install system dependencies & Chromium dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    supervisor \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install SearXNG
RUN git clone https://github.com/searxng/searxng.git /usr/local/searxng && \
    pip install --no-cache-dir -e /usr/local/searxng

# Install Python requirements and Playwright browser
COPY docker/search-mcp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    playwright install chromium

# Copy configuration files
COPY docker/search-mcp/searxng/settings.yml /etc/searxng/settings.yml
COPY docker/search-mcp/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy application source code
COPY src/ /app/src/

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
