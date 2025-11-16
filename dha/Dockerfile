FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir requests beautifulsoup4
COPY scraper.py .
CMD ["python", "scraper.py"]