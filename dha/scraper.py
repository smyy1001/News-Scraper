import os
import re
import json
import time
from typing import Dict, List, Set, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.dha.com.tr"

# Ana haber kategorileri
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
}

# Basit config (ENV’den override edebilirsin)
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
MAX_PER_CATEGORY = int(os.environ.get("MAX_PER_CATEGORY", "0"))  # 0 = limitsiz
MAX_PAGES_PER_CATEGORY = int(os.environ.get("MAX_PAGES_PER_CATEGORY", "50"))
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "0.3"))

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; dha-scraper/1.0; +https://example.com)"
})


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
    """
    Kategori listing HTML’inden haber linklerini çıkarır.
    - son-dakika: her kategoriden son dakika haberleri; slug’a göre değil, genel pattern’e göre bakıyoruz
    - diğerleri: /{kategori_slug}/... pattern’i
    """
    links: List[str] = []

    if category_slug == "son-dakika":
        # /...-123456 gibi biten haber linklerini yakala
        pattern = re.compile(r'href="(/[^"]+?-\\d+)"')
    else:
        # Örn: /gundem/... /spor/...
        pattern = re.compile(r'href="(/%s/[^"]+)"' % re.escape(category_slug))

    for m in pattern.finditer(html):
        href = m.group(1)
        # Foto / video galeri, vb. ele
        if "/foto-" in href or "/video-" in href or "/galeri" in href:
            continue
        full = BASE_URL + href
        links.append(full)

    # Sıralamayı koruyarak duplicate temizle
    seen = set()
    deduped = []
    for u in links:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def parse_article(url: str, html: str, category_slug: str) -> Dict[str, str]:
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

    return {
        "url": url,
        "title": title,
        "category": category,
        "category_slug": category_slug,
        "date_time": date_time,
        "city": city,
        "body": body,
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

        # Sayfa nerdeyse boşsa muhtemelen sonlara geldik
        if len(new_links) < 3:
            print(f"[INFO] [{category_slug}] very few new links, probably end. stop.")
            break

    print(f"[INFO] [{category_slug}] total saved: {count}")


def main():
    print(f"[INFO] Output dir: {OUTPUT_DIR}")
    print(f"[INFO] Max per category: {MAX_PER_CATEGORY or 'no-limit'}")
    print(f"[INFO] Max pages per category: {MAX_PAGES_PER_CATEGORY}")
    print(f"[INFO] Categories: {', '.join(CATEGORIES.keys())}")

    # Global duplicate kontrolü: aynı haber hem Son Dakika’da hem kendi kategorisinde görünürse
    seen_urls: Set[str] = set()

    for slug in CATEGORIES.keys():
        crawl_category(slug, seen_urls)


if __name__ == "__main__":
    main()
