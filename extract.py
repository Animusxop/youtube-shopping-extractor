#!/usr/bin/env python3
"""
Extract tagged products (Amazon + Flipkart + Shopsy) from YouTube videos/Shorts.
Supports both CLI execution and importable library usage for Streamlit.
"""

import re
import sys
import json
import requests
from urllib.parse import urlparse, parse_qs
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

def fetch_page(video_id: str, timeout: int = 15) -> str:
    """Fetch the YouTube page HTML."""
    url = f"https://www.youtube.com/shorts/{video_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text

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

def extract_products(html: str) -> Dict[str, Any]:
    """
    Extract unique Amazon, Flipkart, and Shopsy products from page HTML.
    Returns counts, lists of IDs, titles, and full structured product objects.
    """
    products_list: List[Dict[str, str]] = []
    seen_ids = set()
    amazon_asins = set()
    flipkart_pids = set()

    # 1. Parse structured ytInitialData
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

                # Extract thumbnail
                thumb_list = item.get("thumbnail", {}).get("thumbnails", [])
                thumbnail_url = thumb_list[-1]["url"] if thumb_list else ""

                # Extract target product link
                target_url = ""
                commands = item.get("onClickCommand", {}).get("commandExecutorCommand", {}).get("commands", [])
                for cmd in commands:
                    if "urlEndpoint" in cmd and "url" in cmd["urlEndpoint"]:
                        target_url = cmd["urlEndpoint"]["url"]
                        break

                # Identify platform & product ID
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

    # 2. Fallback regex extraction for IDs
    raw_amazon = set(re.findall(r'amazon\.(?:in|com)/dp/([A-Z0-9]{10})', html))
    raw_flipkart = set(re.findall(r'(?:pid=|productId=)([A-Z0-9]{10,})', html))

    amazon_asins.update(raw_amazon)
    flipkart_pids.update(raw_flipkart)

    # Fallback product titles extraction
    labels = re.findall(r'"label":\s*"((?:[^"\\]|\\.)*)"', html)
    raw_titles = []
    for label in labels:
        label = label.replace('\\u0026', '&')
        if any(m in label.lower() for m in ['amazon', 'flipkart', 'shopsy']):
            clean = re.sub(r',\s*(From|from)\s+(Amazon India|Flipkart|Shopsy By Flipkart).*$', '', label, flags=re.I)
            clean = re.sub(r',\s*¤0\s*.*$', '', clean)
            clean = re.sub(r',\s*Out of stock$', '', clean, flags=re.I)
            raw_titles.append(clean.strip())

    unique_titles = list(dict.fromkeys(raw_titles))

    # Populate fallback items if structured items were not found
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

    # Total counts
    product_renderer_count = html.count('"productListItemRenderer"')

    return {
        "amazon_count": len(amazon_asins),
        "flipkart_count": len(flipkart_pids),
        "total_unique": len(amazon_asins) + len(flipkart_pids),
        "product_renderer_count": product_renderer_count,
        "amazon_asins": sorted(amazon_asins),
        "flipkart_pids": sorted(flipkart_pids),
        "titles": [p["title"] for p in products_list if p.get("title")] or unique_titles,
        "products": products_list,
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract.py <youtube_url>")
        print("Example: python extract.py https://www.youtube.com/shorts/7dhfAlKfFnU")
        sys.exit(1)

    url = sys.argv[1]

    try:
        video_id = extract_video_id(url)
        print(f"Video ID: {video_id}")
        print("Fetching page...")

        html = fetch_page(video_id)
        result = extract_products(html)

        print("\n" + "=" * 50)
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
        elif result['titles']:
            print("\nProduct titles found:")
            for i, title in enumerate(result['titles'], 1):
                print(f"  {i}. {title[:100]}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()