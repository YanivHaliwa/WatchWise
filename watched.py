#!/usr/bin/env python3
import os
import requests
import argparse
import sys

DEBUG = False

ACCESS_TOKEN = os.getenv("TRAKT_ACCESS_TOKEN")
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "trakt-api-version": "2",
    "trakt-api-key": os.getenv("TRAKT_CLIENT_ID")
}

def get_all_watched_titles():
    """Get all watched movie and show titles from Trakt.tv history"""
    titles = set()
    page = 1
    per_page = 100

    while True:
        url = f"https://api.trakt.tv/sync/history?page={page}&limit={per_page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print("❌ Error:", response.status_code, response.text)
            break

        data = response.json()
        if not data:
            break  # no more pages

        for entry in data:
            if entry["type"] == "movie":
                titles.add(entry["movie"]["title"])
            elif entry["type"] == "episode":
                titles.add(entry["show"]["title"])

        if DEBUG:
            print(f"Processed page {page} with {len(data)} entries")
        
        page += 1

    return titles

def print_all_history():
    """Print all watched titles alphabetically"""
    titles = get_all_watched_titles()
    
    print("\n🎬 Watched (Movies & Series):")
    for title in sorted(titles):
        print(f"• {title}")
    
    return titles

def check_if_watched(query):
    """Check if a specific title has been watched"""
    titles = get_all_watched_titles()
    
    # Case-insensitive partial matching
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
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug output")
    
    args = parser.parse_args()
    
    global DEBUG
    if args.debug:
        DEBUG = True
        print("Debug mode enabled")
    
    if not ACCESS_TOKEN or not os.getenv("TRAKT_CLIENT_ID"):
        print("❌ Error: Missing Trakt API credentials")
        print("Please set the TRAKT_ACCESS_TOKEN and TRAKT_CLIENT_ID environment variables")
        sys.exit(1)
    
    if args.query:
        return check_if_watched(args.query)
    else:
        # Default behavior or explicit -a/--all flag
        print_all_history()
        return True

if __name__ == "__main__":
    main()
