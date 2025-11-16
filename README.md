# News-Scraper


## IHA Run:
```
    cd iha
    docker build -t iha-scraper .
    mkdir -p iha_output

    docker run --rm \
    -v "$(pwd)/iha_output:/app/output" \
    iha-scraper
```



## DHA Run:
```
    cd dha
    mkdir -p dha_output
    docker build -t dha-scraper .

    docker run --rm \
    -v "$(pwd)/dha_output:/app/output" \
    dha-scraper
```