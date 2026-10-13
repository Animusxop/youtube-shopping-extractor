#!/usr/bin/env python3
"""
Extract tagged products (Amazon + Flipkart + Shopsy) from YouTube videos/Shorts.
Uses YouTube's official InnerTube API with multiple client fallbacks (MWEB, WEB, HTML),
detailed diagnostics, and optional cookie/proxy support for cloud deployments (Streamlit Cloud).
"""

import re
import sys
import json
import requests
from typing import Dict, Any, List, Optional

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

def _parse_renderers_and_text(renderers: List[Any], raw_text: str) -> Dict[str, Any]:
    """Extract products, counts, and IDs from renderers and raw JSON text."""
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
            "url": target_url or (
                f"https://www.amazon.in/dp/{product_id}" if platform == "Amazon" and product_id
                else f"https://www.flipkart.com/product/p/itme?pid={product_id}" if platform == "Flipkart" and product_id
                else ""
            ),
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

    # Fallback regex extraction for IDs from raw text
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
    }

def get_server_ip() -> str:
    """Get the current outbound public IP of this machine/server."""
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=3)
        return r.json().get("ip", "Unknown")
    except Exception:
        return "Unknown"

def extract_products(
    video_identifier: str,
    gl: str = "IN",
    hl: str = "en",
    cookie: str = "",
    proxy: str = "",
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Extract products using a multi-strategy waterfall:
    Strategy 1: InnerTube MWEB (Mobile Web client - minimal botguard)
    Strategy 2: InnerTube WEB (with official YouTube Web key)
    Strategy 3: HTML Scrape (with consent cookies)
    Records full diagnostics for every attempt.
    """
    try:
        video_id = extract_video_id(video_identifier)
    except Exception:
        video_id = video_identifier.strip()

    proxies_dict = {"http": proxy, "https": proxy} if proxy.strip() else None
    diagnostics = []

    # -------------------------------------------------------------
    # Strategy 1: InnerTube MWEB (Mobile Web)
    # -------------------------------------------------------------
    try:
        url = "https://www.youtube.com/youtubei/v1/next"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "X-YouTube-Client-Name": "2",
            "X-YouTube-Client-Version": "2.20240901.01.00",
            "Origin": "https://m.youtube.com",
            "Referer": f"https://m.youtube.com/shorts/{video_id}",
        }
        if cookie.strip():
            headers["Cookie"] = cookie.strip()

        payload = {
            "context": {
                "client": {
                    "hl": hl,
                    "gl": gl,
                    "clientName": "MWEB",
                    "clientVersion": "2.20240901.01.00",
                }
            },
            "videoId": video_id
        }
        r = requests.post(url, headers=headers, json=payload, timeout=timeout, proxies=proxies_dict)
        raw_text = r.text
        has_prods = "productListItemRenderer" in raw_text

        diagnostics.append({
            "strategy": "InnerTube MWEB",
            "status_code": r.status_code,
            "response_size": len(raw_text),
            "found_renderers": has_prods,
            "error": None if r.status_code == 200 else raw_text[:200],
        })

        if r.status_code == 200 and has_prods:
            data = r.json()
            renderers = _find_keys(data, 'productListItemRenderer')
            result = _parse_renderers_and_text(renderers, raw_text)
            result["source"] = "InnerTube MWEB"
            result["diagnostics"] = diagnostics
            return result

    except Exception as e:
        diagnostics.append({
            "strategy": "InnerTube MWEB",
            "status_code": 0,
            "response_size": 0,
            "found_renderers": False,
            "error": str(e),
        })

    # -------------------------------------------------------------
    # Strategy 2: InnerTube WEB (with official YouTube API key)
    # -------------------------------------------------------------
    try:
        url = "https://www.youtube.com/youtubei/v1/next?key=AIzaSyAO_FJ2SlqAE4OiHsCaJSCQnzmUFXYbFYQ&prettyPrint=false"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "Referer": f"https://www.youtube.com/shorts/{video_id}",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20240901.01.00",
        }
        if cookie.strip():
            headers["Cookie"] = cookie.strip()

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
        r = requests.post(url, headers=headers, json=payload, timeout=timeout, proxies=proxies_dict)
        raw_text = r.text
        has_prods = "productListItemRenderer" in raw_text

        diagnostics.append({
            "strategy": "InnerTube WEB",
            "status_code": r.status_code,
            "response_size": len(raw_text),
            "found_renderers": has_prods,
            "error": None if r.status_code == 200 else raw_text[:200],
        })

        if r.status_code == 200 and has_prods:
            data = r.json()
            renderers = _find_keys(data, 'productListItemRenderer')
            result = _parse_renderers_and_text(renderers, raw_text)
            result["source"] = "InnerTube WEB"
            result["diagnostics"] = diagnostics
            return result

    except Exception as e:
        diagnostics.append({
            "strategy": "InnerTube WEB",
            "status_code": 0,
            "response_size": 0,
            "found_renderers": False,
            "error": str(e),
        })

    # -------------------------------------------------------------
    # Strategy 3: HTML Scrape with consent-bypass cookies
    # -------------------------------------------------------------
    try:
        url = f"https://www.youtube.com/shorts/{video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": f"en-{gl},en;q=0.9",
            "Sec-Fetch-Mode": "navigate",
        }
        cookies_dict = {
            "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
            "PREF": f"f4=4000000&hl={hl}&gl={gl}",
        }
        if cookie.strip():
            headers["Cookie"] = cookie.strip()

        r = requests.get(url, headers=headers, cookies=cookies_dict, timeout=timeout, proxies=proxies_dict)
        html = r.text
        has_prods = "productListItemRenderer" in html

        diagnostics.append({
            "strategy": "HTML Scrape",
            "status_code": r.status_code,
            "response_size": len(html),
            "found_renderers": has_prods,
            "error": None if r.status_code == 200 else html[:200],
        })

        if has_prods:
            data_match = re.search(r'var ytInitialData = ({.*?});</script>', html)
            if not data_match:
                data_match = re.search(r'ytInitialData\s*=\s*({.+?});', html)
            if data_match:
                yt_data = json.loads(data_match.group(1))
                renderers = _find_keys(yt_data, 'productListItemRenderer')
                result = _parse_renderers_and_text(renderers, html)
                result["source"] = "HTML Scrape"
                result["diagnostics"] = diagnostics
                return result

    except Exception as e:
        diagnostics.append({
            "strategy": "HTML Scrape",
            "status_code": 0,
            "response_size": 0,
            "found_renderers": False,
            "error": str(e),
        })

    # Nothing found after all strategies
    return {
        "amazon_count": 0,
        "flipkart_count": 0,
        "total_unique": 0,
        "product_renderer_count": 0,
        "amazon_asins": [],
        "flipkart_pids": [],
        "titles": [],
        "products": [],
        "source": "None",
        "diagnostics": diagnostics,
    }

# Backward compatibility alias
fetch_page = lambda vid, timeout=15: ""

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract.py <youtube_url>")
        print("Example: python extract.py https://www.youtube.com/shorts/7dhfAlKfFnU")
        sys.exit(1)

    url = sys.argv[1]
    res = extract_products(url)
    print("\n" + "=" * 50)
    print(f"Source            : {res.get('source')}")
    print(f"Total Unique      : {res['total_unique']}")
    print(f"Amazon Products   : {res['amazon_count']}")
    print(f"Flipkart Products : {res['flipkart_count']}")
    print("=" * 50)
    for i, p in enumerate(res.get("products", [])[:5], 1):
        print(f"  {i}. [{p['merchant']}] {p['title'][:60]} (ID: {p['product_id']})")

if __name__ == "__main__":
    main()