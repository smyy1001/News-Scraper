from __future__ import annotations

import os
import re
import json
import time
from typing import Dict, TextIO, Tuple, List, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------
#  KATEGORİ TANIMLARI
# ---------------------------------------------------------------------

BASE_DOMAIN = "iha.com.tr"
BASE_URL = f"https://www.{BASE_DOMAIN}"

# slug -> {name (insan okunur), url (listing)}
CATEGORIES: Dict[str, Dict[str, str]] = {
    # "gundem": {
    #     "name": "GÜNDEM",
    #     "url": f"{BASE_URL}/gundem",
    # },
    # "politika": {
    #     "name": "POLİTİKA",
    #     "url": f"{BASE_URL}/politika",
    # },
    # "ekonomi": {
    #     "name": "EKONOMİ",
    #     "url": f"{BASE_URL}/ekonomi",
    # },
    # "dunya": {
    #     "name": "DÜNYA",
    #     "url": f"{BASE_URL}/dunya",
    # },
    # "asayis": {
    #     "name": "ASAYİŞ",
    #     "url": f"{BASE_URL}/asayis",
    # },
    # "spor": {
    #     "name": "SPOR",
    #     "url": f"{BASE_URL}/spor",
    # },
    # "aktuel": {
    #     "name": "AKTÜEL",
    #     "url": f"{BASE_URL}/aktuel",
    # },
    # "saglik": {
    #     "name": "SAĞLIK",
    #     "url": f"{BASE_URL}/saglik",
    # },
    # "cevre": {
    #     "name": "ÇEVRE",
    #     "url": f"{BASE_URL}/cevre",
    # },
    # "magazin": {
    #     "name": "MAGAZİN",
    #     "url": f"{BASE_URL}/magazin",
    # },
    # "kultur_sanat": {
    #     "name": "KÜLTÜR SANAT",
    #     "url": f"{BASE_URL}/kultur-sanat",
    # },
    # "egitim": {
    #     "name": "EĞİTİM",
    #     "url": f"{BASE_URL}/egitim",
    # },
    # "teknoloji": {
    #     "name": "TEKNOLOJİ",
    #     "url": f"{BASE_URL}/teknoloji",
    # },
    # "yerel": {
    #     "name": "YEREL",
    #     "url": f"{BASE_URL}/yerel",
    # },
    "video": {
        "name": "VIDEO", 
        "url": f"{BASE_URL}/video"},
    "foto": {
        "name": "FOTO GALERİ", 
        "url": f"{BASE_URL}/foto"},
}

# ---------------------------------------------------------------------
#  AYARLAR (ENV)
# ---------------------------------------------------------------------

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

_raw_limit = os.environ.get("MAX_ARTICLES", "300")
try:
    MAX_ARTICLES = int(_raw_limit)
except ValueError:
    MAX_ARTICLES = 300

# None -> limitsiz (kategori sayfaları bitene kadar)
ARTICLE_LIMIT: int | None = None if MAX_ARTICLES <= 0 else MAX_ARTICLES

REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "0.7"))
MAX_LISTING_PAGES = int(os.environ.get("MAX_LISTING_PAGES", "2000"))

# ---------------------------------------------------------------------
#  HTTP SESSION
# ---------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    }
)

# ---------------------------------------------------------------------
#  YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------

def normalize_media_url(src: str) -> str:
    src = (src or "").strip()
    if not src:
        return ""

    # protocol-relative //something
    if src.startswith("//"):
        src = "https:" + src
    # root-relative /path
    elif src.startswith("/"):
        src = urljoin(BASE_URL, src)

    return src


def looks_like_image(url: str) -> bool:
    return bool(re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", url, re.IGNORECASE))


def looks_like_video(url: str) -> bool:
    return bool(re.search(r"\.(mp4|webm|m3u8)(\?|$)", url, re.IGNORECASE))


def is_layout_asset(url: str) -> bool:
    """
    Logo, ikon, sprite gibi her haberde tekrarlanan şeyleri kaba filtrele.
    (Gerekiyorsa sonra daha da sıkılaştırırız.)
    """
    lower = url.lower()
    if any(word in lower for word in ["logo", "icon", "sprite", "favicon", "placeholder"]):
        return True
    if lower.endswith(".svg") or lower.endswith(".ico"):
        return True
    return False


def extract_media_links(soup: BeautifulSoup) -> List[str]:
    """
    Haber sayfasındaki görsel + video linklerini toplar.
    Önce main/article içinde arar, yoksa tüm sayfaya bakar.
    """
    root = soup.find("main") or soup.find("article") or soup

    media: List[str] = []
    seen: Set[str] = set()

    # IMG
    for img in root.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if not src:
            continue
        url = normalize_media_url(src)
        if not url:
            continue
        if is_layout_asset(url):
            continue
        if not looks_like_image(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        media.append(url)

    # VIDEO + SOURCE
    for video in root.find_all("video"):
        vsrc = video.get("src")
        if vsrc:
            url = normalize_media_url(vsrc)
            if looks_like_video(url) and url not in seen:
                seen.add(url)
                media.append(url)

        for source in video.find_all("source"):
            ssrc = source.get("src")
            if not ssrc:
                continue
            url = normalize_media_url(ssrc)
            if looks_like_video(url) and url not in seen:
                seen.add(url)
                media.append(url)

    # IFRAMES (gömülü player'lar)
    for iframe in root.find_all("iframe"):
        isrc = iframe.get("src")
        if not isrc:
            continue
        url = normalize_media_url(isrc)
        if is_layout_asset(url):
            continue
        if looks_like_video(url) or "player" in url.lower() or "embed" in url.lower():
            if url not in seen:
                seen.add(url)
                media.append(url)

    return media



def get_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
        return None
    return BeautifulSoup(resp.text, "html.parser")


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if BASE_DOMAIN not in (parsed.netloc or ""):
        return False

    path = (parsed.path or "").rstrip("/")
    if not path:
        return False

    last = path.split("/")[-1]
    # allow normal articles ending with digits
    parts = last.split("-")
    if parts[-1].isdigit():
        return True

    # ALSO allow video/foto slug patterns e.g. starting with 'video-' or 'foto-'
    if last.startswith("video") or last.startswith("foto"):
        return True

    return False



def extract_article_links(listing_url: str, soup: BeautifulSoup) -> Set[str]:
    links: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(listing_url, href)
        if is_article_url(full):
            links.add(full)
    return links


def extract_pagination_links(start_url: str, listing_url: str, soup: BeautifulSoup) -> Set[str]:
    """
    Kategori sayfalarındaki diğer sayfaları yakalamak için:
      /gundem/2.sayfa.html vb.
    Sadece ilgili kategori ağacının altında olan sayfaları alıyoruz.
    """
    pages: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(listing_url, href)
        if BASE_DOMAIN not in full:
            continue
        if "/sayfa" in full and full.startswith(start_url):
            pages.add(full)
    return pages


def extract_city_from_url(url: str) -> str:
    """
    https://www.iha.com.tr/adana-haberleri/...  -> 'adana'
    https://www.iha.com.tr/zonguldak-haberleri/... -> 'zonguldak'
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    first = path.split("/")[0]
    if first.endswith("-haberleri"):
        return first.replace("-haberleri", "")
    return ""


def parse_date_time(soup: BeautifulSoup) -> str:
    """
    Yayın tarih/saat bilgisini almaya çalış:
      1) Meta tag'lerden
      2) Full text içinde '15 Kasım 2025 ... 17:21' benzeri pattern ile
    """
    # 1) Meta
    meta_time = (
        soup.find("meta", attrs={"property": "article:published_time"})
        or soup.find("meta", attrs={"itemprop": "datePublished"})
        or soup.find("meta", attrs={"name": "pubdate"})
        or soup.find("meta", attrs={"name": "date"})
    )
    if meta_time and meta_time.get("content"):
        return meta_time["content"].strip()

    # 2) Full text regex (Türkçe ay isimleri vs. çok kasarız diye daha gevşek tutuyoruz)
    full_text = soup.get_text("\n", strip=True)
    # Örn: '15 Kasım 2025 Cumartesi 17:21'
    dt_regex = re.compile(
        r"\b(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+20\d{2}[^0-9]{0,30}\d{1,2}:\d{2})\b"
    )
    m = dt_regex.search(full_text)
    if m:
        return m.group(1).strip()

    return ""


def parse_article(url: str, soup: BeautifulSoup) -> Dict[str, str]:
    # Başlık
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Tarih/saat
    date_time = parse_date_time(soup)

    # Şehir (URL'den)
    city = extract_city_from_url(url)

    # Gövde
    body_texts: List[str] = []
    main = soup.find("main") or soup.find("article")

    if main:
        for p in main.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if txt:
                body_texts.append(txt)
    else:
        for p in soup.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if txt:
                body_texts.append(txt)

    body = "\n\n".join(body_texts)

    # Medya linkleri (resim + video)
    media_links = extract_media_links(soup)

    return {
        "url": url,
        "title": title,
        "date_time": date_time,
        "city": city,
        "body": body,
        "media_links": media_links,
    }


# ---------------------------------------------------------------------
#  DOSYA YAZMA
# ---------------------------------------------------------------------


def get_file_handle(cat_slug: str, category_files: Dict[str, TextIO]) -> TextIO:
    if cat_slug not in category_files:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"iha_{cat_slug}.jsonl")
        print(f"[INFO]  -> writing category '{cat_slug}' to {path}")
        category_files[cat_slug] = open(path, "a", encoding="utf-8")
    return category_files[cat_slug]


# ---------------------------------------------------------------------
#  KATEGORİ BAZLI CRAWL
# ---------------------------------------------------------------------


def crawl_category(
    cat_slug: str,
    cat_name: str,
    start_url: str,
    category_files: Dict[str, TextIO],
    global_seen_urls: Set[str],
    global_start_count: int,
) -> int:
    """
    Tek bir kategoriyi (örneğin GÜNDEM) crawl eder.
    Geriye bu kategoride kaç yeni haber yazdığını döner.
    """
    visited_listing: Set[str] = set()
    listing_queue: List[str] = [start_url]

    fetched_here = 0

    print(f"[INFO] === CATEGORY {cat_slug} ({cat_name}) ===")
    while (
        listing_queue
        and len(visited_listing) < MAX_LISTING_PAGES
        and (ARTICLE_LIMIT is None or global_start_count + fetched_here < ARTICLE_LIMIT)
    ):
        listing_url = listing_queue.pop(0)
        if listing_url in visited_listing:
            continue
        visited_listing.add(listing_url)

        print(f"[INFO] Fetch listing: {listing_url}")
        soup = get_soup(listing_url)
        if soup is None:
            continue

        # Bu listing sayfasındaki haber linklerini topla
        new_article_links = extract_article_links(listing_url, soup)
        print(
            f"[INFO]   found {len(new_article_links)} article links "
            f"(before dedup: {len(new_article_links)})"
        )

        # Sayfa sayfa pagination linkleri
        new_pages = extract_pagination_links(start_url, listing_url, soup)
        for p in new_pages:
            if p not in visited_listing and p not in listing_queue:
                listing_queue.append(p)

        # Haberleri çek
        fh = get_file_handle(cat_slug, category_files)
        for article_url in sorted(new_article_links):
            # Global dedup: aynı url'yi başka kategoriden görürsek tekrar çekmeyelim
            if article_url in global_seen_urls:
                continue

            if ARTICLE_LIMIT is not None and global_start_count + fetched_here >= ARTICLE_LIMIT:
                break

            print(f"[INFO] Fetch article: {article_url}")
            article_soup = get_soup(article_url)
            if article_soup is None:
                continue

            data = parse_article(article_url, article_soup)
            record = {
                "category": cat_name,
                "date_time": data["date_time"],
                "url": data["url"],
                "title": data["title"],
                "city": data["city"],
                "body": data["body"],
                "media_links": data.get("media_links", []),
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fetched_here += 1
            global_seen_urls.add(article_url)
            time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    print(
        f"[INFO] Category {cat_slug} done. "
        f"Visited listing pages={len(visited_listing)}, fetched articles={fetched_here}"
    )
    return fetched_here


# ---------------------------------------------------------------------
#  ANA CRAWL
# ---------------------------------------------------------------------


def crawl():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    category_files: Dict[str, TextIO] = {}
    global_seen_urls: Set[str] = set()  # tüm kategoriler arası dedup
    total_fetched = 0

    try:
        for slug, cfg in CATEGORIES.items():
            if ARTICLE_LIMIT is not None and total_fetched >= ARTICLE_LIMIT:
                print("[INFO] Global article limit reached, stopping.")
                break

            cat_name = cfg["name"]
            start_url = cfg["url"]

            fetched = crawl_category(
                slug,
                cat_name,
                start_url,
                category_files,
                global_seen_urls,
                total_fetched,
            )
            total_fetched += fetched

        print(f"[INFO] ALL DONE. Total articles fetched: {total_fetched}")
    finally:
        # Dosyaları kapat
        for fh in category_files.values():
            try:
                fh.close()
            except Exception:
                pass


if __name__ == "__main__":
    crawl()
