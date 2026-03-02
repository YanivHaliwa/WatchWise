#!/usr/bin/env python3
import os
import json
import time
import requests
import argparse
import sys
import subprocess

DEBUG = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GET_TRAKT_SCRIPT = os.path.join(SCRIPT_DIR, "getTrakt.sh")
_WATCHED_CACHE_FILE = os.path.join(SCRIPT_DIR, ".watched_cache.json")
_CACHE_TTL = 24 * 3600  # 24 hours

def _load_watched_cache() -> set:
    """Load watched titles from disk cache if it exists and is fresh."""
    try:
        with open(_WATCHED_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'titles' in data and 'ts' in data:
            if time.time() - data['ts'] < _CACHE_TTL:
                return set(data['titles'])
    except Exception:
        pass
    return set()

def _save_watched_cache(titles: set) -> None:
    """Persist watched titles to disk cache with current timestamp."""
    try:
        with open(_WATCHED_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'ts': time.time(), 'titles': list(titles)}, f, ensure_ascii=False)
    except Exception:
        pass

def refresh_tokens():
    """Run getTrakt.sh interactively, then read updated tokens from .zshrc."""
    print("🔄 Access token expired. Re-authenticating with Trakt...")
    result = subprocess.run(["bash", GET_TRAKT_SCRIPT])
    if result.returncode != 0:
        print("❌ Failed to refresh tokens.")
        sys.exit(1)
    zshrc = os.path.expanduser("~/.zshrc")
    with open(zshrc) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export TRAKT_ACCESS_TOKEN="):
                os.environ["TRAKT_ACCESS_TOKEN"] = line.split("=", 1)[1].strip('"')
            elif line.startswith("export TRAKT_REFRESH_TOKEN="):
                os.environ["TRAKT_REFRESH_TOKEN"] = line.split("=", 1)[1].strip('"')
    print("✅ Tokens refreshed. Retrying...")

def get_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('TRAKT_ACCESS_TOKEN', '')}",
        "trakt-api-version": "2",
        "trakt-api-key": os.environ.get("TRAKT_CLIENT_ID", "")
    }

def make_request(url, retried=False):
    response = requests.get(url, headers=get_headers())
    if response.status_code == 401:
        if retried:
            print("❌ Still getting 401 after token refresh. Exiting.")
            sys.exit(1)
        refresh_tokens()
        return make_request(url, retried=True)
    return response

def _fetch_from_trakt() -> set:
    """Fetch all watched titles from Trakt API."""
    titles = set()
    page = 1
    per_page = 100

    while True:
        url = f"https://api.trakt.tv/sync/history?page={page}&limit={per_page}"
        response = make_request(url)
        if response.status_code != 200:
            print("❌ Error:", response.status_code, response.text)
            break

        data = response.json()
        if not data:
            break

        for entry in data:
            if entry["type"] == "movie":
                titles.add(entry["movie"]["title"])
            elif entry["type"] == "episode":
                titles.add(entry["show"]["title"])

        if DEBUG:
            print(f"Processed page {page} with {len(data)} entries")

        page += 1

    return titles

def get_all_watched_titles(force_refresh: bool = False) -> set:
    """Get all watched titles — from disk cache if fresh, else fetch from Trakt."""
    if not force_refresh:
        cached = _load_watched_cache()
        if cached:
            if DEBUG:
                print(f"✅ Loaded {len(cached)} watched titles from cache")
            return cached

    titles = _fetch_from_trakt()
    if titles:
        _save_watched_cache(titles)
        if DEBUG:
            print(f"💾 Saved {len(titles)} watched titles to cache")
    return titles

def print_all_history(force_refresh: bool = False):
    """Print all watched titles alphabetically."""
    titles = get_all_watched_titles(force_refresh=force_refresh)

    print("\n🎬 Watched (Movies & Series):")
    for title in sorted(titles):
        print(f"• {title}")

    return titles

def check_if_watched(query, force_refresh: bool = False):
    """Check if a specific title has been watched."""
    titles = get_all_watched_titles(force_refresh=force_refresh)

    query_lower = query.lower()
    matches = [title for title in titles if query_lower in title.lower()]

    if DEBUG:
        print(f"Query: '{query}'")
        print(f"Found matches: {matches}")

    is_watched = len(matches) > 0

    if is_watched:
        print(f"✅ '{query}' watched!")
        if len(matches) > 1:
            print("Matches found:")
            for match in sorted(matches):
                print(f"• {match}")
    else:
        print(f"❌ '{query}' not watched yet.")

    return is_watched

def main():
    parser = argparse.ArgumentParser(description="Check your Trakt.tv watch history")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Show all watched movies and series")
    parser.add_argument("-q", "--query", type=str,
                        help="Query if a specific title has been watched")
    parser.add_argument("-r", "--refresh", action="store_true",
                        help="Force refresh from Trakt (ignore cache)")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug output")

    args = parser.parse_args()

    global DEBUG
    if args.debug:
        DEBUG = True
        print("Debug mode enabled")

    if not os.environ.get("TRAKT_ACCESS_TOKEN") or not os.environ.get("TRAKT_CLIENT_ID"):
        print("❌ Error: Missing Trakt API credentials")
        print("Please set the TRAKT_ACCESS_TOKEN and TRAKT_CLIENT_ID environment variables")
        sys.exit(1)

    if args.query:
        return check_if_watched(args.query, force_refresh=args.refresh)
    else:
        print_all_history(force_refresh=args.refresh)
        return True

if __name__ == "__main__":
    main()
