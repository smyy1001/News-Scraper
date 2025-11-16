# News Scraper


### IHA:
```
    mkdir -p iha_output
    docker build -t iha-scraper iha/

    docker run --rm \
    -v "$(pwd)/iha_output:/app/output" \
    iha-scraper
```



### DHA:
```
    mkdir -p dha_output
    docker build -t dha-scraper dha/

    docker run --rm \
    -v "$(pwd)/dha_output:/app/output" \
    dha-scraper
```


### İkisini tek seferde beraber çalıştırmak için:
```
    chmod +x run_all.sh
    ./run_all.sh
```