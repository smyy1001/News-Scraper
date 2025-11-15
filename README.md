# News-Scraper


## IHA Run:
```
    cd iha
    docker build -t iha-scraper .
    mkdir -p output

    docker run --rm \
    -e OUTPUT_DIR=output \
    -e MAX_ARTICLES=0 \
    -e REQUEST_DELAY=0.7 \
    -e MAX_LISTING_PAGES=2000 \
    -v "$(pwd)/output:/app/output" \
    iha-scraper
```



## DHA Run:
```
    cd dha
    docker build -t dha-scraper .
    mkdir -p output

    docker run --rm \
    -e OUTPUT_DIR=output \
    -e MAX_ARTICLES=0 \
    -e REQUEST_DELAY=0.7 \
    -e MAX_LISTING_PAGES=2000 \
    -v "$(pwd)/output:/app/output" \
    dha-scraper
```