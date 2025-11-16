# News-Scraper


## IHA Run:
```
    cd iha
    docker build -t iha-scraper .
    mkdir -p iha_output

    docker run --rm \
    -e OUTPUT_DIR=output \
    -e MAX_ARTICLES=0 \
    -e REQUEST_DELAY=0.7 \
    -e MAX_LISTING_PAGES=2000 \
    -v "$(pwd)/iha_output:/app/output" \
    iha-scraper
```



## DHA Run:
```
    cd dha
    mkdir -p dha_output
    docker build -t dha-scraper .

    docker run --rm \
    -e MAX_PER_CATEGORY=0 \
    -e MAX_PAGES_PER_CATEGORY=50 \
    -e REQUEST_DELAY=0.3 \
    -v "$(pwd)/dha_output:/app/output" \
    dha-scraper
```