import os
import re
import json
import time
from typing import Dict, List, Set, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.dha.com.tr"

# ---------------------------------------------------------------------
#  Kategoriler
# ---------------------------------------------------------------------
CATEGORIES: Dict[str, str] = {
    "son-dakika": "Son Dakika",
    "gundem": "Gündem",
    "politika": "Politika",
    "spor": "Spor",
    "dunya": "Dünya",
    "ekonomi": "Ekonomi",
    "kurumsal": "Kurumsal",
    "egitim": "Eğitim",
    "yerel-haberler": "Yerel Haberler",
    "saglik-yasam": "Sağlık-Yaşam",
    "kultur-sanat": "Kültür Sanat",
    "foto-galeri": "Foto Galeri",
    "video": "Video",
}

# ---------------------------------------------------------------------
#  AYARLAR
# ---------------------------------------------------------------------
OUTPUT_DIR = "output"
MAX_PER_CATEGORY = 0
MAX_PAGES_PER_CATEGORY = 50
REQUEST_DELAY = 0.3

# ---------------------------------------------------------------------
#  HTTP SESSION
# ---------------------------------------------------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; dha-scraper/1.0; +https://example.com)"
})
# ---------------------------------------------------------------------


def fetch(url: str) -> Optional[str]:
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"[WARN] {url} status={resp.status_code}")
            return None
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        print(f"[ERROR] fetch failed {url}: {e}")
        return None
    

def extract_article_links(html: str, category_slug: str) -> List[str]:
    links: List[str] = []

    if category_slug == "son-dakika":
        pattern = re.compile(r'href="(/[^"]+?-\\d+)"')
    elif category_slug in {"foto-galeri", "video"}:
        pattern = re.compile(r'href="(/%s/[^"#]+)"' % re.escape(category_slug))
    else:
        pattern = re.compile(r'href="(/%s/[^"]+)"' % re.escape(category_slug))

    for m in pattern.finditer(html):
        href = m.group(1)

        if "javascript:" in href:
            continue

        if category_slug not in {"foto-galeri", "video"}:
            if "/foto-galeri/" in href or "/video/" in href or "/galeri/" in href:
                continue

        full = BASE_URL + href
        links.append(full)

    seen: Set[str] = set()
    deduped: List[str] = []
    for u in links:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped


def normalize_url(src: str) -> str:
    src = src.strip()
    if not src:
        return ""

    if src.startswith("//"):
        src = "https:" + src
    elif src.startswith("/"):
        src = BASE_URL + src

    return src

def canonical_media_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or ""

    if host == "image.dha.com.tr":
        parts = path.split("/")
        if len(parts) >= 6 and parts[1] == "i" and parts[2] == "dha":
            last = parts[-1]
            path = "/i/dha/" + last

    return f"{host}{path}"



def looks_like_image(url: str) -> bool:
    return bool(re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", url, re.IGNORECASE))


def looks_like_video(url: str) -> bool:
    return bool(re.search(r"\.(mp4|webm|m3u8)(\?|$)", url, re.IGNORECASE))


def extract_media_links(soup: BeautifulSoup) -> List[str]:
    media: List[str] = []
    seen_keys: Set[str] = set()

    # IMG
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if not src:
            continue
        url = normalize_url(src)
        if not url:
            continue
        if not looks_like_image(url):
            continue

        key = canonical_media_key(url)
        if key in seen_keys:
            continue

        seen_keys.add(key)
        media.append(url)

    # VIDEO + SOURCE
    for video in soup.find_all("video"):
        vsrc = video.get("src")
        if vsrc:
            url = normalize_url(vsrc)
            if looks_like_video(url):
                key = canonical_media_key(url)
                if key not in seen_keys:
                    seen_keys.add(key)
                    media.append(url)

        for source in video.find_all("source"):
            ssrc = source.get("src")
            if not ssrc:
                continue
            url = normalize_url(ssrc)
            if not looks_like_video(url):
                continue
            key = canonical_media_key(url)
            if key in seen_keys:
                continue
        
            seen_keys.add(key)
            media.append(url)

    # IFRAMES
    for iframe in soup.find_all("iframe"):
        isrc = iframe.get("src")
        if not isrc:
            continue
        url = normalize_url(isrc)
        if looks_like_video(url) or "player" in url.lower() or "embed" in url.lower():
            key = canonical_media_key(url)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            media.append(url)

    return media


def parse_article(url: str, html: str, category_slug: str) -> Dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")

    # Başlık
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Kategori adı
    category = CATEGORIES.get(category_slug, category_slug)

    # Tarih-saat: "14.11.2025 - 16:02" gibi pattern
    full_text = soup.get_text(" ", strip=True)
    dt_match = re.search(r"\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}:\d{2}", full_text)
    date_time = dt_match.group(0) if dt_match else ""

    # Şehir: "ANKARA, (DHA)-" pattern’i
    city = ""
    city_match = re.search(r"\b([A-ZÇĞİÖŞÜ]{3,}),\s*\(DHA\)", full_text)
    if city_match:
        city = city_match.group(1).title()

    # Gövde: tüm <p>’ler (footer / telif uyarılarını kaba filtreyle ele)
    body_parts: List[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        lower = text.lower()
        if "dha.com.tr" in lower or "telif hakkı" in lower or "izin alınmadan" in lower:
            continue
        body_parts.append(text)

    body = "\n\n".join(body_parts)

    # MEDYA LİNKLERİ
    media_links = extract_media_links(soup)

    return {
        "category": category,
        "category_slug": category_slug,
        "date_time": date_time,
        "url": url,
        "title": title,        
        "city": city,
        "body": body,
        "media_links": media_links,
    }


def crawl_category(category_slug: str, seen_urls: Set[str]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"dha_{category_slug}.jsonl")

    count = 0
    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        if MAX_PER_CATEGORY and count >= MAX_PER_CATEGORY:
            break

        if page == 1:
            url = f"{BASE_URL}/{category_slug}/"
        else:
            url = f"{BASE_URL}/{category_slug}/?page={page}"

        print(f"[INFO] [{category_slug}] listing page {page}: {url}")
        html = fetch(url)
        if not html:
            print(f"[INFO] [{category_slug}] no HTML, stop at page {page}")
            break

        links = extract_article_links(html, category_slug)
        print(f"[INFO]   found {len(links)} raw links")

        new_links = [u for u in links if u not in seen_urls]
        print(f"[INFO]   new links this page: {len(new_links)}")
        if not new_links:
            print(f"[INFO] [{category_slug}] no new links, stop.")
            break

        with open(out_path, "a", encoding="utf-8") as fh:
            for article_url in new_links:
                if MAX_PER_CATEGORY and count >= MAX_PER_CATEGORY:
                    break
                time.sleep(REQUEST_DELAY)
                a_html = fetch(article_url)
                if not a_html:
                    continue
                data = parse_article(article_url, a_html, category_slug)
                fh.write(json.dumps(data, ensure_ascii=False) + "\n")
                seen_urls.add(article_url)
                count += 1
                print(f"[INFO]     saved {article_url}")

        if len(new_links) < 3:
            print(f"[INFO] [{category_slug}] very few new links, probably end. stop.")
            break

    print(f"[INFO] [{category_slug}] total saved: {count}")


def main():
    print(f"[INFO] Output dir: {OUTPUT_DIR}")
    print(f"[INFO] Max per category: {MAX_PER_CATEGORY or 'no-limit'}")
    print(f"[INFO] Max pages per category: {MAX_PAGES_PER_CATEGORY}")
    print(f"[INFO] Categories: {', '.join(CATEGORIES.keys())}")

    seen_urls: Set[str] = set()

    for slug in CATEGORIES.keys():
        crawl_category(slug, seen_urls)


if __name__ == "__main__":
    main()
