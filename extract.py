#!/usr/bin/env python3
"""
Extract tagged products (Amazon + Flipkart + Shopsy) from YouTube videos/Shorts.
Uses YouTube's official InnerTube API (reliable on cloud servers & Streamlit Cloud)
with fallback to HTML scraping and consent-bypassing headers.
"""

import re
import sys
import json
import requests
from typing import Dict, Any, List

def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")

def _find_keys(obj: Any, target_key: str) -> List[Any]:
    """Recursively search for a key in a nested dict/list."""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key:
                results.append(v)
            else:
                results.extend(_find_keys(v, target_key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_keys(item, target_key))
    return results

def _find_first_url(obj: Any) -> str:
    """Recursively search for the first urlEndpoint URL."""
    if isinstance(obj, dict):
        if "urlEndpoint" in obj and "url" in obj["urlEndpoint"]:
            return obj["urlEndpoint"]["url"]
        for v in obj.values():
            u = _find_first_url(v)
            if u:
                return u
    elif isinstance(obj, list):
        for item in obj:
            u = _find_first_url(item)
            if u:
                return u
    return ""

def fetch_innertube(video_id: str, gl: str = "IN", hl: str = "en", timeout: int = 15) -> Dict[str, Any]:
    """
    Fetch shopping product tags using YouTube's InnerTube API.
    Works reliably on cloud servers (Streamlit Cloud, AWS, GCP) without consent blocks.
    """
    url = "https://www.youtube.com/youtubei/v1/next"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": "2.20240901.01.00",
    }
    payload = {
        "context": {
            "client": {
                "hl": hl,
                "gl": gl,
                "clientName": "WEB",
                "clientVersion": "2.20240901.01.00",
            }
        },
        "videoId": video_id
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    raw_text = resp.text
    data = resp.json()

    renderers = _find_keys(data, 'productListItemRenderer')
    amazon_asins = set()
    flipkart_pids = set()

    parsed_items = []
    for item in renderers:
        title = item.get("title", {}).get("simpleText") or ""
        merchant = item.get("merchantName", "").strip()
        thumb_list = item.get("thumbnail", {}).get("thumbnails", [])
        thumbnail_url = thumb_list[-1]["url"] if thumb_list else ""
        target_url = _find_first_url(item)

        platform = "Other"
        product_id = ""
        if target_url:
            asin_match = re.search(r'amazon\.(?:in|com)/dp/([A-Z0-9]{10})', target_url)
            pid_match = re.search(r'(?:pid=|productId=)([A-Z0-9]{10,})', target_url)
            if asin_match:
                platform = "Amazon"
                product_id = asin_match.group(1)
                amazon_asins.add(product_id)
            elif pid_match:
                platform = "Flipkart" if "flipkart" in target_url.lower() else "Shopsy"
                product_id = pid_match.group(1)
                flipkart_pids.add(product_id)

        if platform == "Other":
            m_lower = merchant.lower()
            if "amazon" in m_lower:
                platform = "Amazon"
            elif "flipkart" in m_lower:
                platform = "Flipkart"
            elif "shopsy" in m_lower:
                platform = "Shopsy"

        parsed_items.append({
            "title": title,
            "merchant": merchant or platform,
            "platform": platform,
            "product_id": product_id,
            "url": target_url or (f"https://www.amazon.in/dp/{product_id}" if platform == "Amazon" and product_id else f"https://www.flipkart.com/product/p/itme?pid={product_id}" if platform == "Flipkart" and product_id else ""),
            "thumbnail": thumbnail_url,
        })

    # Deduplicate: prefer items that have product_id/url
    products_by_title = {}
    for item in parsed_items:
        t_key = item["title"].strip()
        if not t_key:
            continue
        if t_key not in products_by_title:
            products_by_title[t_key] = item
        else:
            if item["product_id"] and not products_by_title[t_key]["product_id"]:
                products_by_title[t_key] = item

    # Raw search fallback for ASINs/PIDs
    raw_amazon = set(re.findall(r'amazon\.(?:in|com)/dp/([A-Z0-9]{10})', raw_text))
    raw_flipkart = set(re.findall(r'(?:pid=|productId=)([A-Z0-9]{10,})', raw_text))
    amazon_asins.update(raw_amazon)
    flipkart_pids.update(raw_flipkart)

    final_products = list(products_by_title.values())

    return {
        "amazon_count": len(amazon_asins),
        "flipkart_count": len(flipkart_pids),
        "total_unique": len(amazon_asins) + len(flipkart_pids),
        "product_renderer_count": len(renderers),
        "amazon_asins": sorted(amazon_asins),
        "flipkart_pids": sorted(flipkart_pids),
        "titles": [p["title"] for p in final_products if p.get("title")],
        "products": final_products,
        "source": "innertube_api"
    }

def fetch_page_html(video_id: str, timeout: int = 15) -> str:
    """Fetch YouTube page HTML with consent-bypass cookies."""
    url = f"https://www.youtube.com/shorts/{video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Sec-Fetch-Mode": "navigate",
    }
    cookies = {
        "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",  # Consent bypass
        "PREF": "f4=4000000&hl=en&gl=IN",                    # Region lock to India
    }
    resp = requests.get(url, headers=headers, cookies=cookies, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def extract_products_from_html(html: str) -> Dict[str, Any]:
    """Fallback parser for direct HTML response."""
    products_list = []
    seen_ids = set()
    amazon_asins = set()
    flipkart_pids = set()

    data_match = re.search(r'var ytInitialData = ({.*?});</script>', html)
    if not data_match:
        data_match = re.search(r'ytInitialData\s*=\s*({.+?});', html)

    if data_match:
        try:
            yt_data = json.loads(data_match.group(1))
            renderers = _find_keys(yt_data, 'productListItemRenderer')
            for item in renderers:
                title = item.get("title", {}).get("simpleText") or ""
                merchant = item.get("merchantName", "").strip()
                thumb_list = item.get("thumbnail", {}).get("thumbnails", [])
                thumbnail_url = thumb_list[-1]["url"] if thumb_list else ""
                target_url = _find_first_url(item)

                platform = "Other"
                product_id = ""
                if target_url:
                    asin_match = re.search(r'amazon\.(?:in|com)/dp/([A-Z0-9]{10})', target_url)
                    pid_match = re.search(r'(?:pid=|productId=)([A-Z0-9]{10,})', target_url)
                    if asin_match:
                        platform = "Amazon"
                        product_id = asin_match.group(1)
                        amazon_asins.add(product_id)
                    elif pid_match:
                        platform = "Flipkart" if "flipkart" in target_url.lower() else "Shopsy"
                        product_id = pid_match.group(1)
                        flipkart_pids.add(product_id)

                if not platform or platform == "Other":
                    m_lower = merchant.lower()
                    if "amazon" in m_lower:
                        platform = "Amazon"
                    elif "flipkart" in m_lower:
                        platform = "Flipkart"
                    elif "shopsy" in m_lower:
                        platform = "Shopsy"

                key = product_id or target_url or title
                if key and key not in seen_ids:
                    seen_ids.add(key)
                    products_list.append({
                        "title": title,
                        "merchant": merchant or platform,
                        "platform": platform,
                        "product_id": product_id,
                        "url": target_url,
                        "thumbnail": thumbnail_url,
                    })
        except Exception:
            pass

    raw_amazon = set(re.findall(r'amazon\.(?:in|com)/dp/([A-Z0-9]{10})', html))
    raw_flipkart = set(re.findall(r'(?:pid=|productId=)([A-Z0-9]{10,})', html))
    amazon_asins.update(raw_amazon)
    flipkart_pids.update(raw_flipkart)

    if not products_list:
        for asin in sorted(raw_amazon):
            products_list.append({
                "title": "",
                "merchant": "Amazon India",
                "platform": "Amazon",
                "product_id": asin,
                "url": f"https://www.amazon.in/dp/{asin}",
                "thumbnail": "",
            })
        for pid in sorted(raw_flipkart):
            products_list.append({
                "title": "",
                "merchant": "Flipkart",
                "platform": "Flipkart",
                "product_id": pid,
                "url": f"https://www.flipkart.com/product/p/itme?pid={pid}",
                "thumbnail": "",
            })

    return {
        "amazon_count": len(amazon_asins),
        "flipkart_count": len(flipkart_pids),
        "total_unique": len(amazon_asins) + len(flipkart_pids),
        "product_renderer_count": html.count('"productListItemRenderer"'),
        "amazon_asins": sorted(amazon_asins),
        "flipkart_pids": sorted(flipkart_pids),
        "titles": [p["title"] for p in products_list if p.get("title")],
        "products": products_list,
        "source": "html_scrape"
    }

def extract_products(video_identifier: str, gl: str = "IN", hl: str = "en", timeout: int = 15) -> Dict[str, Any]:
    """
    Main extraction function.
    Can accept either a video_id (or full URL) OR raw html string for backward compatibility.
    Primary: InnerTube API (reliable on cloud servers).
    Fallback: HTML scraper.
    """
    # Backward compatibility: if passed full HTML content
    if len(video_identifier) > 50 and ("<html" in video_identifier.lower() or "ytInitialData" in video_identifier):
        return extract_products_from_html(video_identifier)

    # Extract video ID if given a URL
    try:
        video_id = extract_video_id(video_identifier)
    except Exception:
        video_id = video_identifier.strip()

    # 1. Primary Attempt: InnerTube API
    try:
        res = fetch_innertube(video_id, gl=gl, hl=hl, timeout=timeout)
        if res["total_unique"] > 0 or res["products"]:
            return res
    except Exception as e:
        pass

    # 2. Fallback Attempt: Direct HTML Fetch
    try:
        html = fetch_page_html(video_id, timeout=timeout)
        res_html = extract_products_from_html(html)
        if res_html["total_unique"] > 0 or res_html["products"]:
            return res_html
    except Exception:
        pass

    # Return empty result structure if nothing found
    return {
        "amazon_count": 0,
        "flipkart_count": 0,
        "total_unique": 0,
        "product_renderer_count": 0,
        "amazon_asins": [],
        "flipkart_pids": [],
        "titles": [],
        "products": [],
        "source": "none"
    }

# Backward compatibility alias
fetch_page = fetch_page_html

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract.py <youtube_url>")
        print("Example: python extract.py https://www.youtube.com/shorts/7dhfAlKfFnU")
        sys.exit(1)

    url = sys.argv[1]

    try:
        video_id = extract_video_id(url)
        print(f"Video ID: {video_id}")
        print("Extracting tagged products (via InnerTube API / Cloud Safe)...")

        result = extract_products(video_id)

        print("\n" + "=" * 50)
        print(f"Source            : {result.get('source')}")
        print(f"Amazon products   : {result['amazon_count']}")
        print(f"Flipkart products : {result['flipkart_count']}")
        print(f"Total unique      : {result['total_unique']}")
        print(f"(Renderer count)  : {result['product_renderer_count']}")
        print("=" * 50)

        if result['products']:
            print("\nProducts found:")
            for i, p in enumerate(result['products'], 1):
                title = p.get('title') or '(No Title)'
                merchant = p.get('merchant') or p.get('platform')
                pid = p.get('product_id') or 'N/A'
                print(f"  {i}. [{merchant}] {title[:80]} (ID: {pid})")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()