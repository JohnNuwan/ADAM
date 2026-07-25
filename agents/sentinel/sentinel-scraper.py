#!/usr/bin/env python3
"""ADAM-SENTINEL — Scraper web robuste pour la veille technologique.
Utilise requests + beautifulsoup4 pour extraire les titres des sites de reference."""

import json
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Sites de reference et selecteurs CSS pour les titres
SITES = {
    "cybersec": {
        "url": "https://thehackernews.com",
        "selectors": ["h2 a", "h3 a", ".story-title a", "h2.entry-title a"],
    },
    "ai-ml": {
        "url": "https://www.marktechpost.com",
        "selectors": ["h2 a", "h3 a", ".post-title a", "article h2 a"],
    },
    "osint": {
        "url": "https://www.osintme.com",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".entry-title a"],
    },
    "devops": {
        "url": "https://devops.com",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".entry-title a"],
    },
    "cloud": {
        "url": "https://aws.amazon.com/blogs/aws/",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".blog-post-title a"],
    },
    "design": {
        "url": "https://www.smashingmagazine.com/articles/",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".article-title a"],
    },
    "blockchain": {
        "url": "https://cointelegraph.com",
        "selectors": ["h2 a", "h3 a", ".post-title a", "article h2 a"],
    },
    "crypto": {
        "url": "https://decrypt.co",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".post-title a"],
    },
    "network": {
        "url": "https://blog.cloudflare.com",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".post-title a"],
    },
    "programmation": {
        "url": "https://dev.to",
        "selectors": ["h2 a", "h3 a", "article h2 a", ".crayons-story__title a"],
    },
}

def scrape_site(domain, config):
    """Scrape les titres d'un site de reference."""
    results = []
    try:
        if config.get("json", False):
            # API JSON (Reddit)
            resp = requests.get(config["url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # Navigate json_path
            items = data
            for key in config["json_path"]:
                items = items.get(key, [])
            for item in items[:10]:
                title = item
                for key in config["title_key"]:
                    title = title.get(key, "") if isinstance(title, dict) else ""
                if title:
                    results.append(title)
        else:
            resp = requests.get(config["url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            seen = set()
            for selector in config["selectors"]:
                for elem in soup.select(selector):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 10 and text not in seen:
                        seen.add(text)
                        results.append(text)
                    if len(results) >= 10:
                        break
                if len(results) >= 10:
                    break
    except Exception as e:
        results.append(f"[ERREUR] {e}")
    return results[:10]

def main():
    """Scrape tous les domaines et sort du JSON."""
    all_results = {}
    for domain, config in SITES.items():
        try:
            titles = scrape_site(domain, config)
            all_results[domain] = titles
        except Exception as e:
            all_results[domain] = [f"[ERREUR] {e}"]
    
    print(json.dumps(all_results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()