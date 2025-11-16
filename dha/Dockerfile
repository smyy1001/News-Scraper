FROM python:3.11-slim

WORKDIR /app

# Bağımlılıklar
RUN pip install --no-cache-dir requests beautifulsoup4

# Scraper dosyasını kopyala
COPY scraper.py .

# Çıktı klasörü
ENV OUTPUT_DIR=/app/output
ENV MAX_PER_CATEGORY=0
ENV MAX_PAGES_PER_CATEGORY=50
ENV REQUEST_DELAY=0.3

CMD ["python", "scraper.py"]
