import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import yt_dlp

DATA_FILE = "feed_data.json"

YT_SHORTS_QUERIES = [
    "free fire shorts edit #shorts",
    "pubg mobile shorts edit #shorts",
    "anime edit #shorts",
    "gaming viral shorts #shorts",
]
YT_VIDEOS_QUERIES = [
    "free fire highlights montage",
    "pubg mobile viral montage",
    "anime amv edit 4k",
]
PINTEREST_QUERIES = [
    "anime aesthetic wallpaper",
    "gaming neon wallpaper",
    "free fire wallpaper",
    "pubg wallpaper",
    "cyberpunk wallpaper",
    "dark aesthetic art",
]


def load_existing_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("videos", [])
                data.setdefault("shorts", [])
                data.setdefault("photos", [])
                data.setdefault("last_updated", "")
                return data
        except Exception:
            pass
    return {"last_updated": "", "videos": [], "shorts": [], "photos": []}


def fetch_youtube(queries, count, is_short=False):
    results = []
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
        "nocheckcertificate": True,
    }
    per_query = max(5, (count // len(queries)) + 4)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for q in queries:
            if len(results) >= count:
                break
            try:
                info = ydl.extract_info(f"ytsearch{per_query}:{q}", download=False)
                for entry in info.get("entries", []) or []:
                    if len(results) >= count:
                        break
                    vid_id = entry.get("id")
                    title = entry.get("title", "Viral Gaming Edit")
                    duration = entry.get("duration") or 0

                    if is_short and duration > 75:
                        continue
                    if not is_short and 0 < duration < 75:
                        continue

                    if vid_id and not any(r["id"] == vid_id for r in results):
                        results.append({
                            "id": vid_id,
                            "platform": "youtube",
                            "type": "short" if is_short else "video",
                            "title": title,
                            "thumbnail": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
                            "embed_url": f"https://www.youtube.com/embed/{vid_id}?autoplay=1&rel=0&modestbranding=1",
                            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })
            except Exception as e:
                print(f"YouTube warning ({q}): {e}")
    return results[:count]


def extract_unique_pin_urls(html_text):
    raw = re.findall(
        r"https://i\.pinimg\.com/(?:originals|736x|564x|474x)/[a-zA-Z0-9/_-]+\.(?:jpg|jpeg|png|webp)",
        html_text,
    )
    cleaned = []
    seen_hashes = set()
    for url in raw:
        # Image hash/filename ke hisaab se duplicate block karna
        base_name = url.split("/")[-1].split("?")[0]
        if base_name in seen_hashes:
            continue
        seen_hashes.add(base_name)
        cleaned.append(url)
    return cleaned


def fetch_pinterest_photos(count=20, existing_photos=None):
    existing_photos = existing_photos or []
    existing_urls = {p.get("image_url") for p in existing_photos}
    existing_names = {
        (p.get("image_url", "").split("/")[-1].split("?")[0])
        for p in existing_photos
    }

    photos = []
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for q in PINTEREST_QUERIES:
        if len(photos) >= count:
            break
        encoded = urllib.parse.quote(q)
        # Pehle RSS feed try karte hain, phir search HTML page
        endpoints = [
            f"https://www.pinterest.com/search/pins/?q={encoded}&rs=typed",
            f"https://www.pinterest.com/search/pins/?q={encoded}%20aesthetic&rs=typed",
        ]
        for ep in endpoints:
            if len(photos) >= count:
                break
            try:
                resp = requests.get(ep, headers=headers, timeout=12, verify=False)
                urls = extract_unique_pin_urls(resp.text)
                for img_url in urls:
                    if len(photos) >= count:
                        break
                    fname = img_url.split("/")[-1].split("?")[0]
                    if img_url in existing_urls or fname in existing_names:
                        continue
                    if any(p["image_url"] == img_url for p in photos):
                        continue

                    existing_names.add(fname)
                    photos.append({
                        "id": f"pin_{abs(hash(img_url))}",
                        "platform": "pinterest",
                        "title": f"{q.title()} #{len(photos)+1}",
                        "image_url": img_url,
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
            except Exception as e:
                print(f"Pinterest warning ({q}): {e}")

    return photos[:count]


def prepend_without_losing_old(new_items, old_items):
    # Purani koi item auto-delete nahi hogi; naye items upar add honge
    new_ids = {item["id"] for item in new_items}
    kept_old = [item for item in old_items if item["id"] not in new_ids]
    return new_items + kept_old


def main():
    print("[*] Fetching viral content...")
    data = load_existing_data()

    new_shorts = fetch_youtube(YT_SHORTS_QUERIES, count=15, is_short=True)
    new_videos = fetch_youtube(YT_VIDEOS_QUERIES, count=5, is_short=False)
    new_photos = fetch_pinterest_photos(count=20, existing_photos=data.get("photos", []))

    data["shorts"] = prepend_without_losing_old(new_shorts, data.get("shorts", []))
    data["videos"] = prepend_without_losing_old(new_videos, data.get("videos", []))
    data["photos"] = prepend_without_losing_old(new_photos, data.get("photos", []))
    data["last_updated"] = datetime.now().strftime("%d %b %Y, %I:%M %p")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(
        f"[+] Done! Added {len(new_shorts)} Shorts, "
        f"{len(new_videos)} Videos, {len(new_photos)} Photos. "
        f"(Total stored: {len(data['shorts'])} Shorts, {len(data['videos'])} Videos, {len(data['photos'])} Photos)"
    )


if __name__ == "__main__":
    main()
