#!/usr/bin/env python3
from tmdbv3api import TMDb, Movie, TV, Genre
import sys
import os
import argparse

import subprocess
import time as _startup_timer

# Import the watched script functionality
try:
    from watched import get_all_watched_titles, check_if_watched
except ImportError:
    print("Warning: watched.py module not found. Not-watched filtering will be unavailable.")
    get_all_watched_titles = None

# Define color codes
class Colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    MAGENTA = '\033[35m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

DEBUG = False

# ── Persistent translation cache ──────────────────────────────────────────────
# Translations never change, so we persist them to disk across all sessions.
_TRANS_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.trans_cache.json')

def _load_trans_cache() -> dict:
    try:
        import json as _j
        with open(_TRANS_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = _j.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}

def _save_trans_cache(cache: dict) -> None:
    try:
        import json as _j
        with open(_TRANS_CACHE_FILE, 'w', encoding='utf-8') as f:
            _j.dump(cache, f, ensure_ascii=False, indent=None)
    except Exception:
        pass

_trans_cache: dict = _load_trans_cache()   # loaded from disk on startup

import atexit as _atexit
_atexit.register(lambda: _save_trans_cache(_trans_cache))  # auto-save on exit

# ── Persistent watched cache (survives restarts; Trakt syncs in background) ──
_WATCHED_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.watched_cache.json')

def _load_watched_file() -> set:
    """Load watched titles from disk cache (fast, no network)."""
    try:
        import json as _j
        with open(_WATCHED_CACHE_FILE, 'r', encoding='utf-8') as f:
            return set(_j.load(f).get('titles', []))
    except Exception:
        return set()

def _save_watched_file(titles: set) -> None:
    """Persist watched titles to disk cache."""
    try:
        import json as _j, datetime as _dt
        with open(_WATCHED_CACHE_FILE, 'w', encoding='utf-8') as f:
            _j.dump({'titles': sorted(titles), 'updated': _dt.datetime.now().isoformat()}, f)
    except Exception:
        pass

# ── Persistent trailer cache ──────────────────────────────────────────────────
_TRAILER_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.trailer_cache.json')
_IMAGE_CACHE_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.image_cache')

def _load_trailer_file() -> dict:
    """Load trailer keys from disk cache."""
    try:
        import json as _j
        with open(_TRAILER_CACHE_FILE, 'r', encoding='utf-8') as f:
            return _j.load(f)
    except Exception:
        return {}

def _save_trailer_file(cache: dict) -> None:
    try:
        import json as _j
        with open(_TRAILER_CACHE_FILE, 'w', encoding='utf-8') as f:
            _j.dump(cache, f)
    except Exception:
        pass

def _image_disk_path(poster_path: str) -> str:
    import hashlib
    ext = os.path.splitext(poster_path)[1] or '.jpg'
    fname = hashlib.md5(poster_path.encode()).hexdigest() + ext
    return os.path.join(_IMAGE_CACHE_DIR, fname)

def _get_image_from_disk(poster_path: str):
    """Returns (bytes, content_type) or None."""
    try:
        fpath = _image_disk_path(poster_path)
        with open(fpath, 'rb') as f:
            data = f.read()
        ext = os.path.splitext(fpath)[1].lower().lstrip('.')
        ct = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext, 'image/jpeg')
        return data, ct
    except Exception:
        return None

def _save_image_to_disk(poster_path: str, data: bytes) -> None:
    try:
        os.makedirs(_IMAGE_CACHE_DIR, exist_ok=True)
        with open(_image_disk_path(poster_path), 'wb') as f:
            f.write(data)
    except Exception:
        pass

# ── 1 GB combined disk cache size limit ───────────────────────────────────────
_CACHE_SIZE_LIMIT = 1 * 1024 ** 3  # 1 GB

def _total_cache_size() -> int:
    """Return combined bytes of all disk cache files."""
    total = 0
    for f in [_TRANS_CACHE_FILE, _TRAILER_CACHE_FILE, _WATCHED_CACHE_FILE]:
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    if os.path.isdir(_IMAGE_CACHE_DIR):
        for fname in os.listdir(_IMAGE_CACHE_DIR):
            try:
                total += os.path.getsize(os.path.join(_IMAGE_CACHE_DIR, fname))
            except OSError:
                pass
    return total

def _auto_clear_if_over_limit() -> bool:
    """Clear ALL disk caches if combined size exceeds 1 GB. Returns True if cleared."""
    if _total_cache_size() < _CACHE_SIZE_LIMIT:
        return False
    import shutil
    for f in [_TRANS_CACHE_FILE, _TRAILER_CACHE_FILE, _WATCHED_CACHE_FILE]:
        try:
            os.remove(f)
        except OSError:
            pass
    shutil.rmtree(_IMAGE_CACHE_DIR, ignore_errors=True)
    print("[cache] Combined disk size exceeded 1 GB — all disk caches cleared")
    return True

# ── In-memory search cache (current session only — TMDB results can change) ───
_search_cache: dict = {}  # (query, year, genre, limit, desc_length) → {movies:[...], tvs:[...]}

# ISO 639-1 → full language name (for badge display + --lang filter)
_LANG_NAMES: dict = {
    'en': 'English', 'he': 'Hebrew', 'fr': 'French', 'de': 'German',
    'es': 'Spanish', 'it': 'Italian', 'ja': 'Japanese', 'ko': 'Korean',
    'zh': 'Chinese', 'hi': 'Hindi', 'ar': 'Arabic', 'pt': 'Portuguese',
    'ru': 'Russian', 'tr': 'Turkish', 'nl': 'Dutch', 'sv': 'Swedish',
    'da': 'Danish', 'fi': 'Finnish', 'no': 'Norwegian', 'pl': 'Polish',
    'th': 'Thai', 'id': 'Indonesian', 'ms': 'Malay', 'vi': 'Vietnamese',
    'cs': 'Czech', 'hu': 'Hungarian', 'ro': 'Romanian', 'uk': 'Ukrainian',
    'bn': 'Bengali', 'fa': 'Persian', 'ur': 'Urdu', 'ta': 'Tamil',
    'te': 'Telugu', 'ml': 'Malayalam', 'sr': 'Serbian', 'hr': 'Croatian',
    'bg': 'Bulgarian', 'sk': 'Slovak', 'el': 'Greek', 'ca': 'Catalan',
    'nb': 'Norwegian', 'cn': 'Cantonese', 'tl': 'Filipino', 'is': 'Icelandic',
}
#   Stores raw English items. type/nw/translate applied at retrieval time.

def strip_niqqud(s):
    """Remove Hebrew niqqud (vowel marks) from string."""
    return ''.join(c for c in s if not (0x0591 <= ord(c) <= 0x05C7))

def translate_he(text: str) -> str:
    """Translate text to Hebrew using GoogleTranslator."""
    if not text:
        return text
    if text in _trans_cache:
        return _trans_cache[text]
    translated = None
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='auto', target='iw').translate(text)
        if result:
            translated = strip_niqqud(result)
    except Exception as e:
        if DEBUG:
            print(f"Translation error: {e}")
    if translated is None:
        translated = text
    _trans_cache[text] = translated
    return translated


def translate_batch_he(texts: list, max_workers: int = 40) -> list:
    """Translate a list of texts to Hebrew in parallel threads (truly concurrent).
    Already-cached strings are returned instantly without any network call."""
    if not texts:
        return [], 0, 0
    from concurrent.futures import ThreadPoolExecutor
    from deep_translator import GoogleTranslator

    # Split into cached (instant) and uncached (need network)
    output = [None] * len(texts)
    uncached: list = []  # (original_index, text)
    for i, text in enumerate(texts):
        if not text:
            output[i] = text
        elif text in _trans_cache:
            output[i] = _trans_cache[text]
        else:
            uncached.append((i, text))

    if uncached:
        import time as _time_tr

        def _one(idx_text):
            _, text = idx_text
            for attempt in range(3):
                try:
                    result = GoogleTranslator(source='auto', target='iw').translate(text)
                    return strip_niqqud(result) if result else text
                except Exception:
                    if attempt < 2:
                        _time_tr.sleep(0.3 * (attempt + 1))  # 0.3s, 0.6s then give up
            return text  # all retries failed — return original

        workers = min(max_workers, len(uncached), 10)  # cap at 10 to avoid rate limits
        with ThreadPoolExecutor(max_workers=workers) as ex:
            translated = list(ex.map(_one, uncached))
        for (orig_idx, orig_text), tr in zip(uncached, translated):
            _trans_cache[orig_text] = tr
            output[orig_idx] = tr

        # Auto-save after every batch of new translations so progress survives crashes
        _save_trans_cache(_trans_cache)

    n_cached = len(texts) - len(uncached)
    return output, n_cached, len(uncached)


def _parallel_translate_terminal(items: list, max_workers: int = 40) -> None:
    """Parallel-translate title/overview/genres in place for terminal display."""
    if not items:
        return
    flat: list = []
    fmap: list = []
    for idx, item in enumerate(items):
        flat.append(item['title']);                    fmap.append((idx, 'title',  None))
        flat.append(item.get('overview', ''));         fmap.append((idx, 'overview', None))
        for gi, g in enumerate(item.get('genres', [])):
            flat.append(g);                            fmap.append((idx, 'genre', gi))
    translated, _, _ = translate_batch_he(flat)
    for (idx, field, gi), tr in zip(fmap, translated):
        item = items[idx]
        if field == 'title':
            item['title_he'] = tr
        elif field == 'overview':
            item['overview'] = tr
        elif field == 'genre' and gi is not None:
            item['genres'][gi] = tr

def _relevance_score(title: str, overview: str, query: str, whole_word: bool = False) -> int:
    """Score how well a result matches the query (higher = better match).

    4 — full query phrase as whole words in title
    3 — every individual query word as whole word in title
    2 — any query word in title  (substring when whole_word=False, exact word when True)
    1 — any query word in description  (same)
    0 — no match → exclude from results
    """
    import re as _re
    if not query:
        return 1  # browse mode — include everything
    q  = query.strip().lower()
    tl = title.lower()
    ol = (overview or '').lower()
    words = q.split()

    # Score 4: full phrase as whole words in title
    if _re.search(r'\b' + _re.escape(q) + r'\b', tl):
        return 4

    # Score 3: all individual words as whole words in title
    if words and all(_re.search(r'\b' + _re.escape(w) + r'\b', tl) for w in words):
        return 3

    if whole_word:
        # Strict: word must appear as a standalone word (\bword\b)
        if any(_re.search(r'\b' + _re.escape(w) + r'\b', tl) for w in words):
            return 2
        if any(_re.search(r'\b' + _re.escape(w) + r'\b', ol) for w in words):
            return 1
    else:
        # Loose: substring anywhere in title/description
        if any(w in tl for w in words):
            return 2
        if any(w in ol for w in words):
            return 1

    return 0  # no match


# Configuration - adjust these values to control results
MAX_RESULTS_PER_CATEGORY = 20  # Maximum number of results to show for movies and TV shows
DESCRIPTION_LENGTH = 1000  # Number of characters to show from description (0 for full description)

# Parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Search for movies and TV shows from TMDB API",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("query", nargs="*", help="Search query (title or keywords). Optional if -y or -g is provided.")

    parser.add_argument("-m", "--movies-only",
                        action="store_true",
                        help="Show only movie results")

    parser.add_argument("-s", "--series-only",
                        action="store_true",
                        help="Show only TV series results")

    parser.add_argument("-y", "--year",
                        type=int,
                        help="Filter results by specific year (query optional)")

    parser.add_argument("-g", "--genre",
                        nargs='*', metavar='GENRE',
                        help="Filter by genre(s). Examples: -g Action, -g Action Comedy (query optional)")

    parser.add_argument("--lang",
                        nargs='*', metavar='LANGUAGE',
                        help="Filter by original language full name. Examples: --lang English, --lang Korean Japanese")

    parser.add_argument("-l", "--limit",
                        type=int,
                        default=MAX_RESULTS_PER_CATEGORY,
                        help=f"Maximum number of results to show (default: {MAX_RESULTS_PER_CATEGORY})")

    parser.add_argument("-n", "--not-watched",
                        action="store_true",
                        help="Show only titles that haven't been watched yet")

    parser.add_argument("-d", "--desc-length",
                        type=int,
                        default=DESCRIPTION_LENGTH,
                        help=f"Number of characters to show from description (0 for full description, default: {DESCRIPTION_LENGTH})")

    parser.add_argument("-t", "--translate",
                        action="store_true",
                        help="Translate descriptions and genres to Hebrew using GoogleTranslator")

    parser.add_argument("--debug",
                        action="store_true",
                        help="Enable debug output")

    parser.add_argument("-w", "--web",
                        action="store_true",
                        help="Display results in a nice webpage (opens Firefox)")

    parser.add_argument("-i", "--interactive",
                        action="store_true",
                        help="Add live interactive filter panel to the webpage (requires -w)")

    parser.add_argument("--clear-cache",
                        action="store_true",
                        help="Clear all persistent caches (translation, trailer, images, watched) and exit")

    args = parser.parse_args()

    # Handle --clear-cache before anything else
    if args.clear_cache:
        cleared = []
        if os.path.exists(_TRANS_CACHE_FILE):
            size_kb = os.path.getsize(_TRANS_CACHE_FILE) // 1024
            os.remove(_TRANS_CACHE_FILE)
            _trans_cache.clear()
            cleared.append(f"translation ({size_kb} KB)")
        else:
            cleared.append("translation (already empty)")
        n = len(_search_cache)
        _search_cache.clear()
        cleared.append(f"search ({n} entries)")
        import shutil as _shutil
        if os.path.exists(_TRAILER_CACHE_FILE):
            os.remove(_TRAILER_CACHE_FILE)
            cleared.append("trailer (disk)")
        if os.path.isdir(_IMAGE_CACHE_DIR):
            count = len(os.listdir(_IMAGE_CACHE_DIR))
            _shutil.rmtree(_IMAGE_CACHE_DIR, ignore_errors=True)
            cleared.append(f"images ({count} files)")
        if os.path.exists(_WATCHED_CACHE_FILE):
            os.remove(_WATCHED_CACHE_FILE)
            cleared.append("watched (disk)")
        print(f"{Colors.GREEN}Caches cleared: {', '.join(cleared)}{Colors.END}")
        raise SystemExit(0)

    # Convert query list to string
    args.query = " ".join(args.query) if args.query else ""

    # Convert genre list to comma-separated string
    if args.genre:
        args.genre = ", ".join(args.genre)
    else:
        args.genre = ""

    # Normalize lang to list of capitalized names (or None)
    if args.lang:
        args.lang = [l.strip().capitalize() for l in args.lang if l.strip()]
    else:
        args.lang = []

    # Validate: query required unless -y or -g is given, or interactive mode (browser provides input)
    if not args.query and not args.year and not args.genre and not args.interactive:
        parser.error("query is required unless -y/--year or -g/--genre is specified")

    # Apply debug setting
    global DEBUG
    DEBUG = args.debug

    # Check for watched module if --not-watched was specified
    if args.not_watched and get_all_watched_titles is None:
        print(f"{Colors.RED}Error: Cannot use --not-watched flag. watched.py module is not available.{Colors.END}")
        sys.exit(1)

    # --interactive requires --web
    if args.interactive and not args.web:
        parser.error("--interactive (-i) requires --web (-w)")

    return args

# Get command line arguments
args = parse_arguments()
query = args.query

# Web mode result storage
web_movie_items = []
web_tv_items = []

# Load watched titles in background thread (parallel with TMDB search, same as web mode)
watched_titles_lower: set = set()
_nw_load_secs: float = 0.0
_nw_event = None
_nw_container: list = []

if args.not_watched and get_all_watched_titles is not None:
    import threading as _nw_thread_mod
    _nw_event = _nw_thread_mod.Event()

    def _load_nw_bg():
        try:
            ws = get_all_watched_titles()
            _nw_container.append({t.lower() for t in ws})
            if DEBUG:
                print(f"Loaded {len(ws)} watched titles for filtering")
        except Exception as e:
            print(f"{Colors.RED}Error loading watched titles: {e}{Colors.END}")
            print("Continuing without watched filtering")
            _nw_container.append(set())
        _nw_event.set()

    _nw_thread_mod.Thread(target=_load_nw_bg, daemon=True).start()

tmdb = TMDb()
tmdb.api_key = os.getenv("TMDB_API_KEY")
if not tmdb.api_key:
    print(f"{Colors.RED}Error: TMDB_API_KEY environment variable not set.{Colors.END}")
    print(f"Please set it with: export TMDB_API_KEY=your_api_key")
    sys.exit(1)
    
if DEBUG:
    print(f"Using API key: {tmdb.api_key}")
    print(f"Search query: {query}")
    print(f"Movies only: {args.movies_only}")
    print(f"Series only: {args.series_only}")
    print(f"Not watched only: {args.not_watched}")
    print(f"Year filter: {args.year}")
    print(f"Genre filter: {args.genre}")
    print(f"Result limit: {args.limit}")
    print(f"Description length: {args.desc_length}")

tmdb.language = "en"

movie = Movie()
tv = TV()
genre = Genre()

# Get genre lists for movies and TV shows once to use for lookups
import threading as _genres_thread_mod

movie_genres: dict = {}
tv_genres: dict = {}
movie_genre_ids: dict = {}
tv_genre_ids: dict = {}
_genres_ready_event = _genres_thread_mod.Event()

_interactive_blank = args.interactive and not args.query and not args.year and not args.genre

def _load_genres_sync() -> None:
    """Load genre maps from TMDB (called synchronously or in a thread)."""
    global movie_genres, tv_genres, movie_genre_ids, tv_genre_ids
    try:
        movie_genres = {g.id: g.name for g in genre.movie_list()}
        tv_genres = {g.id: g.name for g in genre.tv_list()}
        movie_genre_ids = {v.lower(): k for k, v in movie_genres.items()}
        tv_genre_ids = {v.lower(): k for k, v in tv_genres.items()}
    except Exception as e:
        if DEBUG:
            print(f"Error loading genres: {e}")

if _interactive_blank:
    # Interactive with no initial filters: skip TMDB at startup, load genres in background
    def _bg_genres():
        _load_genres_sync()
        _genres_ready_event.set()
    _genres_thread_mod.Thread(target=_bg_genres, daemon=True).start()
else:
    if args.interactive:
        print(f"{Colors.CYAN}⏳ Connecting to TMDB...{Colors.END}", flush=True)
    _t0 = _startup_timer.time()
    _load_genres_sync()
    _genres_ready_event.set()
    _tmdb_genre_load_secs = round(_startup_timer.time() - _t0, 3)
    if args.interactive:
        print(f"{Colors.GREEN}✓ TMDB ready in {_tmdb_genre_load_secs:.2f}s{Colors.END}", flush=True)

def get_genre_id(genre_name, is_movie=True):
    """Resolve genre name to TMDB genre id."""
    genre_map = movie_genre_ids if is_movie else tv_genre_ids
    name_lower = genre_name.lower()
    # exact match
    if name_lower in genre_map:
        return genre_map[name_lower]
    # partial match
    for k, v in genre_map.items():
        if name_lower in k or k in name_lower:
            return v
    return None

def browse_by_genre_year(genre_id=None, year=None, is_movie=True, limit=20, lang_code=None):
    """Discover movies/TV by genre and/or year via TMDB discover API."""
    import requests as _req
    api_key = os.getenv("TMDB_API_KEY", "")
    media = "movie" if is_movie else "tv"
    url = f"https://api.themoviedb.org/3/discover/{media}"
    params = {"api_key": api_key, "language": "en-US", "sort_by": "popularity.desc", "page": 1}
    if genre_id:
        params["with_genres"] = str(genre_id)
    if lang_code:
        params["with_original_language"] = lang_code
    if year:
        if is_movie:
            params["primary_release_year"] = year
        else:
            params["first_air_date_year"] = year

    results = []
    page = 1
    while len(results) < limit:
        params["page"] = page
        try:
            resp = _req.get(url, params=params, timeout=10)
            data = resp.json()
            items = data.get("results", [])
            if not items:
                break
            results.extend(items)
            if page >= data.get("total_pages", 1):
                break
            page += 1
        except Exception as e:
            if DEBUG:
                print(f"Error in browse discover: {e}")
            break

    # Convert dicts to simple objects for consistent field access
    class R:
        def __init__(self, d, is_movie):
            self.id = d.get("id")
            self.overview = d.get("overview", "")
            self.genre_ids = d.get("genre_ids", [])
            self.original_language = d.get("original_language", "")
            self.poster_path = d.get("poster_path", "")
            if is_movie:
                self.title = d.get("title", "")
                self.release_date = d.get("release_date", "")
            else:
                self.name = d.get("name", "")
                self.first_air_date = d.get("first_air_date", "")

    return [R(d, is_movie) for d in results[:limit]]


def _tmdb_discover(is_movie=True, **kwargs):
    """Direct TMDB discover API call returning simple objects."""
    import requests as _req
    api_key = os.getenv("TMDB_API_KEY", "")
    media = "movie" if is_movie else "tv"
    url = f"https://api.themoviedb.org/3/discover/{media}"
    params = {"api_key": api_key, "language": "en-US", "sort_by": "popularity.desc", "page": 1, **kwargs}
    try:
        resp = _req.get(url, params=params, timeout=10)
        items = resp.json().get("results", [])
    except Exception:
        return []

    class R:
        def __init__(self, d):
            self.id = d.get("id")
            self.overview = d.get("overview", "")
            self.genre_ids = d.get("genre_ids", [])
            self.original_language = d.get("original_language", "")
            self.title = d.get("title", "")
            self.name = d.get("name", "")
            self.release_date = d.get("release_date", "")
            self.first_air_date = d.get("first_air_date", "")
            self.poster_path = d.get("poster_path", "")

    return [R(d) for d in items]

def search_in_description(query, is_movie=True, limit=15, year_filter=None, whole_word: bool = False):
    """
    Search for a term in descriptions by getting more results and directly searching them.
    
    Args:
        query (str): The search query
        is_movie (bool): Whether to search for movies (True) or TV shows (False)
        limit (int): Maximum number of results to return
        year_filter (int, optional): Filter results by specific year
        
    Returns:
        list: List of results matching the search criteria
    """
    found_in_description = []
    
    try:
        # Convert query to lowercase for case-insensitive matching
        query_lower = query.lower()
        # Split the query into individual words for better matching
        query_words = query_lower.split()
        
        # Instead of just searching predefined lists, also search directly for the term
        api_search_results = []
        if is_movie:
            # First, search for more movies directly (this will help find matching descriptions)
            try:
                # Get at least 5 pages of results to search more thoroughly
                for page in range(1, 6):
                    search_results = movie.search(query, page=page)
                    if search_results:
                        api_search_results.extend(search_results)
            except Exception as e:
                if DEBUG:
                    print(f"Error in direct movie search: {e}")
                
            # Get a larger set of movies to search through - more pages for more thorough search
            sources = [
                movie.popular(page=1),
                movie.popular(page=2),
                movie.popular(page=3),
                movie.top_rated(page=1),
                movie.top_rated(page=2),
                movie.top_rated(page=3),
                movie.now_playing(page=1),
                movie.now_playing(page=2)
            ]
            
            # Try to get upcoming movies if available
            try:
                sources.append(movie.upcoming(page=1))
                sources.append(movie.upcoming(page=2))
            except:
                pass
            
            # If year filter is specified, also search for movies from that year specifically
            if year_filter:
                try:
                    year_results = _tmdb_discover(is_movie=True, primary_release_year=year_filter)
                    sources.append(year_results)
                    if DEBUG:
                        print(f"Added {len(year_results)} movies from year {year_filter}")
                except Exception as e:
                    if DEBUG:
                        print(f"Error fetching movies from year {year_filter}: {e}")
                
        else:
            # First, search for more TV shows directly
            try:
                # Get at least 5 pages of results
                for page in range(1, 6):
                    search_results = tv.search(query, page=page)
                    if search_results:
                        api_search_results.extend(search_results)
            except Exception as e:
                if DEBUG:
                    print(f"Error in direct TV search: {e}")
                
            # For TV shows, get multiple pages of results for a deeper search
            sources = [
                tv.popular(page=1),
                tv.popular(page=2),
                tv.popular(page=3),
                tv.top_rated(page=1),
                tv.top_rated(page=2),
                tv.top_rated(page=3),
                tv.on_the_air(page=1),
                tv.on_the_air(page=2)
            ]
            
            # Try to get airing today if available
            try:
                sources.append(tv.airing_today(page=1))
                sources.append(tv.airing_today(page=2))
            except:
                pass
            
            # If year filter is specified, also search for TV shows from that year
            if year_filter:
                try:
                    # For TV shows, we'll use first_air_date_year parameter
                    year_results = _tmdb_discover(is_movie=False, first_air_date_year=year_filter)
                    sources.append(year_results)
                    if DEBUG:
                        print(f"Added {len(year_results)} TV shows from year {year_filter}")
                except Exception as e:
                    if DEBUG:
                        print(f"Error fetching TV shows from year {year_filter}: {e}")
        
        # Combine all sources for searching
        all_results = api_search_results.copy()  # Start with the direct search results
        for source in sources:
            all_results.extend(source)
            
        # Remove duplicates by ID
        unique_ids = set()
        unique_results = []
        for item in all_results:
            if hasattr(item, 'id') and item.id not in unique_ids:
                unique_results.append(item)
                unique_ids.add(item.id)
        
        if DEBUG:
            print(f"Searching through {len(unique_results)} {'movie' if is_movie else 'TV'} items")
        
        # Now search through FULL descriptions with improved matching
        count = 0
        for item in unique_results:
            # Apply year filter if specified
            if year_filter:
                item_year = None
                
                if is_movie and hasattr(item, 'release_date') and item.release_date:
                    try:
                        item_year = int(item.release_date.split('-')[0])
                    except (ValueError, IndexError):
                        pass
                elif not is_movie and hasattr(item, 'first_air_date') and item.first_air_date:
                    try:
                        item_year = int(item.first_air_date.split('-')[0])
                    except (ValueError, IndexError):
                        pass
                
                if item_year != year_filter:
                    continue  # Skip items that don't match the year filter
            
            if hasattr(item, 'overview') and item.overview:
                # Search the entire description
                item_overview_lower = item.overview.lower()
                item_title_lower = (item.title if hasattr(item, 'title') else item.name).lower() if hasattr(item, 'name') or hasattr(item, 'title') else ""
                
                # Different ways to match:
                # 1. Direct substring match for the full query
                # 2. Check if ALL words in the query are in the description (partial match)
                # 3. Check if at least half of the words in the query are in the description
                
                import re as _re_sd
                if whole_word:
                    direct_match = bool(_re_sd.search(r'\b' + _re_sd.escape(query_lower) + r'\b', item_overview_lower))
                    word_matches = sum(
                        1 for q_word in query_words
                        if _re_sd.search(r'\b' + _re_sd.escape(q_word) + r'\b', item_overview_lower)
                    )
                else:
                    direct_match = query_lower in item_overview_lower
                    words_in_overview = [word.strip('.,!?:;()[]{}"\'-') for word in item_overview_lower.split()]
                    word_matches = sum(1 for q_word in query_words if any(q_word in w or w in q_word for w in words_in_overview))

                # Match criteria
                if len(query_words) == 1:
                    match_found = direct_match
                else:
                    # For multi-word queries, require either a direct match or at least 70% of words
                    match_threshold = max(1, int(len(query_words) * 0.7))
                    match_found = direct_match or word_matches >= match_threshold
                
                if match_found:
                    if DEBUG:
                        print(f"Found match in description: {item.title if is_movie else item.name}")
                        print(f"Match type: {'Direct match' if direct_match else f'Word match ({word_matches}/{len(query_words)} words)'}")
                        
                        # Find the match in the description and show context
                        desc_lower = item.overview.lower()
                        if direct_match:
                            match_pos = desc_lower.find(query_lower)
                            start_pos = max(0, match_pos - 30)
                            end_pos = min(len(desc_lower), match_pos + len(query_lower) + 30)
                            context = item.overview[start_pos:end_pos]
                            print(f"Match context: ...{context}...")
                    
                    # Make sure it's not a title match too (for cleaner results distinction)
                    title = item.title if is_movie else item.name
                    if title and not any(q_word in title.lower() for q_word in query_words):
                        found_in_description.append(item)
                        count += 1
                        if count >= limit:
                            break
    
    except Exception as e:
        if DEBUG:
            print(f"Error in description search: {e}")
    
    return found_in_description

# Helper function to highlight search terms in overview text
def highlight_search_terms(overview, query, query_words):
    overview_lower = overview.lower()
    query_lower = query.lower()
    highlighted = False
    
    # First try direct match of the full query
    if query_lower in overview_lower:
        # Direct match
        idx = overview_lower.find(query_lower)
        before = overview[:idx]
        term = overview[idx:idx+len(query)]
        after = overview[idx+len(query):]
        overview = f"{before}{Colors.BOLD}{Colors.RED}{term}{Colors.END}{after}"
        highlighted = True
    
    # If no direct match, try to highlight individual query words
    if not highlighted and len(query_words) > 0:
        for q_word in query_words:
            if q_word in overview_lower and len(q_word) > 2:  # Only highlight words with 3+ chars
                idx = overview_lower.find(q_word)
                word_len = len(q_word)
                # Get the actual case-preserved word from the original text
                before = overview[:idx]
                term = overview[idx:idx+word_len]
                after = overview[idx+word_len:]
                overview = f"{before}{Colors.BOLD}{Colors.RED}{term}{Colors.END}{after}"
                highlighted = True
                break
    
    # If still no highlight, look for partial word matches
    if not highlighted:
        words_in_overview = [word.strip('.,!?:;()[]{}"\'-') for word in overview_lower.split()]
        for word in words_in_overview:
            for q_word in query_words:
                if (q_word in word or word in q_word) and len(q_word) > 2:
                    # Find this word in the original text
                    word_start = overview_lower.find(word)
                    if word_start >= 0:
                        word_end = word_start + len(word)
                        before = overview[:word_start]
                        term = overview[word_start:word_end]
                        after = overview[word_end:]
                        overview = f"{before}{Colors.BOLD}{Colors.RED}{term}{Colors.END}{after}"
                        highlighted = True
                        break
            if highlighted:
                break
                
    return overview


def highlight_search_terms_html(text, query, query_words):
    """Highlight search terms in text with HTML mark tags (no ANSI)."""
    import html as _html
    if not query:
        return _html.escape(text)
    text_lower = text.lower()
    query_lower = query.lower()
    # Direct match
    if query_lower in text_lower:
        idx = text_lower.find(query_lower)
        before = _html.escape(text[:idx])
        term = _html.escape(text[idx:idx + len(query_lower)])
        after = _html.escape(text[idx + len(query_lower):])
        return f'{before}<mark class="hl">{term}</mark>{after}'
    # Word-level match
    for q_word in query_words:
        if len(q_word) > 2 and q_word in text_lower:
            idx = text_lower.find(q_word)
            before = _html.escape(text[:idx])
            term = _html.escape(text[idx:idx + len(q_word)])
            after = _html.escape(text[idx + len(q_word):])
            return f'{before}<mark class="hl">{term}</mark>{after}'
    return _html.escape(text)


def generate_html(movie_items, tv_items, args, query, interactive=False, watched_titles=None):
    """Generate a beautiful dark-themed HTML page for search results."""
    import html as _html
    import datetime
    import json

    rtl = args.translate
    direction = "rtl" if rtl else "ltr"
    side = "right" if rtl else "left"
    lang = "he" if rtl else "en"
    q_display = _html.escape(query) if query else "(browse)"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    today_str = datetime.date.today().isoformat()
    watched_set = watched_titles or set()

    # Collect all unique genres for the interactive datalist
    all_genres = sorted({g for item in (movie_items + tv_items) for g in item['genres']})

    def make_card(item, kind):
        prefix = item['prefix']
        raw_date = item['date'] or ''
        is_future = bool(raw_date and raw_date > today_str)
        title = _html.escape(item['title'])
        date = _html.escape(raw_date)
        genres = item['genres']
        full_ov = item['overview'] or "No overview available."
        q = item['query']
        q_words = item['query_words']
        desc_len = item['desc_length']

        # Build display overview (truncated + highlighted)
        display_ov = full_ov
        if desc_len > 0 and len(display_ov) > desc_len:
            display_ov = display_ov[:desc_len] + "..."
        is_desc = prefix == "🔍"
        if q and is_desc:
            ov_html = highlight_search_terms_html(display_ov, q, q_words)
        else:
            ov_html = _html.escape(display_ov)

        lang_code = item.get('lang', '')
        lang_name = item.get('lang_name', '') or lang_code
        lang_badge = f'<span class="lang-badge">{_html.escape(lang_name)}</span>' if lang_name else ''
        genre_badges = "".join(
            f'<span class="badge">{_html.escape(g)}</span>' for g in genres
        ) + lang_badge
        icon = "🔍" if is_desc else ("🎬" if kind == "movie" else "📺")
        future_cls = " future-card" if is_future else ""
        css_extra = (" desc-match" if is_desc else "") + future_cls
        soon_badge = '<span class="soon-badge">🔜 Coming Soon</span>' if is_future else ""

        # Data attributes for interactive JS filtering
        year_val = raw_date[:4] if raw_date and len(raw_date) >= 4 else ""
        genres_val = "|".join(g.lower() for g in genres)
        is_watched = item['title'].lower() in watched_set
        full_ov_attr = _html.escape(full_ov, quote=True)

        return f'''<div class="card {kind}-card{css_extra}" \
data-type="{kind}" data-year="{year_val}" data-genres="{genres_val}" \
data-watched="{'true' if is_watched else 'false'}" \
data-full-overview="{full_ov_attr}" data-desc-len="{desc_len}">
  <div class="card-top">
    <span class="icon">{icon}</span>
    <div class="card-main">
      <div class="card-header">
        <span class="card-title">{title}</span>
        <span class="card-date">{date}{soon_badge}</span>
      </div>
      <div class="genres">{genre_badges}</div>
    </div>
  </div>
  <div class="overview">{ov_html}</div>
</div>'''

    def build_section(items, kind, label, icon_emoji):
        if args.series_only and kind == "movie":
            return ""
        if args.movies_only and kind == "tv":
            return ""
        # Prominent filter chips
        chips = []
        if query:
            chips.append(f'<span class="fchip fchip-query">🔍 {q_display}</span>')
        if args.year:
            chips.append(f'<span class="fchip fchip-year">📅 {args.year}</span>')
        if args.genre:
            chips.append(f'<span class="fchip fchip-genre">🎭 {_html.escape(args.genre)}</span>')
        if args.not_watched:
            chips.append('<span class="fchip fchip-nw">👁 Unwatched</span>')
        if args.translate:
            chips.append('<span class="fchip fchip-lang">🌐 Hebrew</span>')
        if not chips:
            chips.append('<span class="fchip fchip-browse">✦ Browse All</span>')
        chips_html = " ".join(chips)
        # Sort ascending by date (earliest first)
        sorted_items = sorted(items, key=lambda x: x.get('date', '') or '')
        cards_html = "\n".join(make_card(it, kind) for it in sorted_items)
        if not cards_html:
            cards_html = '<p class="empty">No results found.</p>'
        count = len(items)
        return f'''<section class="{kind}-section" data-section="{kind}">
  <div class="sec-title">
    <span class="sec-label">{icon_emoji} {label}</span>
    <div class="sec-chips">{chips_html}</div>
    <span class="sec-count" id="count-{kind}">{count} results</span>
  </div>
  <div class="grid" id="grid-{kind}">{cards_html}</div>
</section>'''

    movies_sec = build_section(movie_items, "movie", "Movies", "🎬")
    tv_sec = build_section(tv_items, "tv", "TV Series", "📺")

    # ── Interactive filter panel ──────────────────────────────────────────────
    genre_options = "\n".join(
        f'<option value="{_html.escape(g)}">' for g in all_genres
    )
    watched_available = "true" if watched_set else "false"
    init_type = "movie" if args.movies_only else ("tv" if args.series_only else "all")
    init_year = str(args.year) if args.year else ""
    init_genre = args.genre if args.genre else ""
    init_limit = str(args.limit)
    init_desc = str(args.desc_length)
    init_nw = "true" if args.not_watched else "false"

    filter_panel = f"""
<div id="filter-bar">
  <div class="fb-title">🔧 Filters</div>
  <div class="fb-row">
    <div class="fb-group">
      <label>Type</label>
      <select id="f-type">
        <option value="all"{'  selected' if init_type=='all' else ''}>All</option>
        <option value="movie"{'  selected' if init_type=='movie' else ''}>Movies only</option>
        <option value="tv"{'  selected' if init_type=='tv' else ''}>TV Series only</option>
      </select>
    </div>
    <div class="fb-group">
      <label>Year</label>
      <input id="f-year" type="text" placeholder="e.g. 2025" value="{init_year}" maxlength="4">
    </div>
    <div class="fb-group">
      <label>Genre</label>
      <input id="f-genre" type="text" placeholder="e.g. Action" value="{init_genre}" list="genre-list">
      <datalist id="genre-list">{genre_options}</datalist>
    </div>
    <div class="fb-group">
      <label>Limit <span class="fb-hint">(0 = all)</span></label>
      <input id="f-limit" type="number" min="0" value="{init_limit}">
    </div>
    <div class="fb-group">
      <label>Desc chars <span class="fb-hint">(0 = full)</span></label>
      <input id="f-desc" type="number" min="0" step="100" value="{init_desc}">
    </div>
    <div class="fb-group fb-check">
      <label>
        <input id="f-nw" type="checkbox" {'checked' if args.not_watched else ''} {'disabled' if not watched_set else ''}>
        Not watched only
        {'<span class="fb-hint">(no data)</span>' if not watched_set else ''}
      </label>
    </div>
    <div class="fb-group">
      <button id="btn-clear">✕ Clear</button>
    </div>
  </div>
  <div class="fb-status" id="fb-status"></div>
</div>
""" if interactive else ""

    filter_js = f"""
<script>
(function() {{
  const watchedAvailable = {watched_available};
  const defaultDesc = {init_desc};

  function val(id) {{ return document.getElementById(id); }}

  function applyFilters() {{
    const fType  = val('f-type').value;
    const fYear  = val('f-year').value.trim();
    const fGenre = val('f-genre').value.trim().toLowerCase();
    const fLimit = parseInt(val('f-limit').value) || 0;
    const fDesc  = parseInt(val('f-desc').value);
    const fNW    = val('f-nw').checked;

    let total = 0, visible = 0;
    const counts = {{ movie: 0, tv: 0 }};
    const shown  = {{ movie: 0, tv: 0 }};

    document.querySelectorAll('.card').forEach(card => {{
      const t   = card.dataset.type;
      const yr  = card.dataset.year;
      const grs = card.dataset.genres;
      const wtc = card.dataset.watched === 'true';
      total++;

      // type filter
      if (fType !== 'all' && t !== fType) {{ card.style.display = 'none'; return; }}
      // year filter
      if (fYear && yr !== fYear) {{ card.style.display = 'none'; return; }}
      // genre filter
      if (fGenre && !grs.includes(fGenre)) {{ card.style.display = 'none'; return; }}
      // not-watched filter
      if (fNW && watchedAvailable && wtc) {{ card.style.display = 'none'; return; }}
      // limit filter (per section)
      counts[t]++;
      if (fLimit > 0 && counts[t] > fLimit) {{ card.style.display = 'none'; return; }}

      card.style.display = '';
      shown[t]++;
      visible++;

      // desc-length filter: update overview text
      const ov = card.querySelector('.overview');
      if (ov) {{
        const full = card.dataset.fullOverview || '';
        if (!isNaN(fDesc) && fDesc > 0 && full.length > fDesc) {{
          ov.textContent = full.substring(0, fDesc) + '...';
        }} else {{
          ov.textContent = full;
        }}
      }}
    }});

    // Update section counts
    ['movie','tv'].forEach(k => {{
      const el = document.getElementById('count-' + k);
      if (el) el.textContent = shown[k] + ' results';
      const sec = document.querySelector('.' + k + '-section');
      if (sec) sec.style.display = shown[k] === 0 && counts[k] === 0 ? 'none' : '';
    }});

    // Section visibility based on type filter
    if (fType === 'movie') {{
      const tv = document.querySelector('.tv-section');
      if (tv) tv.style.display = 'none';
    }} else if (fType === 'tv') {{
      const mv = document.querySelector('.movie-section');
      if (mv) mv.style.display = 'none';
    }} else {{
      document.querySelectorAll('section').forEach(s => s.style.display = '');
    }}

    val('fb-status').textContent = visible + ' of ' + total + ' results shown';
  }}

  function clearFilters() {{
    val('f-type').value  = 'all';
    val('f-year').value  = '';
    val('f-genre').value = '';
    val('f-limit').value = '0';
    val('f-desc').value  = String(defaultDesc);
    val('f-nw').checked  = false;
    applyFilters();
  }}

  ['f-type','f-year','f-genre','f-limit','f-desc','f-nw'].forEach(id => {{
    const el = val(id);
    if (el) el.addEventListener('input', applyFilters);
    if (el) el.addEventListener('change', applyFilters);
  }});
  val('btn-clear').addEventListener('click', clearFilters);

  applyFilters();
}})();
</script>
""" if interactive else ""

    # ── CSS ──────────────────────────────────────────────────────────────────
    top_offset = "130px" if interactive else "0"
    css = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: linear-gradient(135deg, #09090f 0%, #0c1220 55%, #09090f 100%);
  color: #dde1ef;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  min-height: 100vh;
  direction: {direction};
  padding-bottom: 48px;
}}
header {{
  background: linear-gradient(90deg, #12002b, #0a1525, #00122b);
  border-bottom: 2px solid #7c3aed;
  padding: 18px 32px;
  position: sticky; top: 0; z-index: 100;
  backdrop-filter: blur(10px);
}}
header h1 {{ font-size: 1.7rem; color: #a78bfa; font-weight: 800; letter-spacing: .4px; }}
header .sub {{ color: #4b5563; font-size: .82rem; margin-top: 4px; }}

/* ── Filter bar ── */
#filter-bar {{
  position: sticky; top: 68px; z-index: 90;
  background: linear-gradient(90deg, #0d0d20, #0a1020);
  border-bottom: 1px solid #2d1f5e;
  padding: 12px 28px 10px;
  backdrop-filter: blur(12px);
}}
.fb-title {{ font-size: .75rem; color: #7c3aed; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }}
.fb-row {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }}
.fb-group {{ display: flex; flex-direction: column; gap: 4px; }}
.fb-group label {{ font-size: .75rem; color: #6b7280; font-weight: 600; }}
.fb-group input[type=text],
.fb-group input[type=number],
.fb-group select {{
  background: #111827; color: #e2e8f0; border: 1px solid #2d3748;
  border-radius: 6px; padding: 6px 10px; font-size: .85rem; outline: none;
  min-width: 90px;
}}
.fb-group input:focus, .fb-group select:focus {{ border-color: #7c3aed; box-shadow: 0 0 0 2px rgba(124,58,237,.25); }}
.fb-check {{ justify-content: flex-end; padding-bottom: 2px; }}
.fb-check label {{
  display: flex; align-items: center; gap: 9px; cursor: pointer;
  color: #c4b5fd; font-size: 1rem; font-weight: 700;
  background: #1a1035; border: 1.5px solid #3b2a6e;
  border-radius: 8px; padding: 6px 12px;
}}
.fb-check label:hover {{ background: #221445; border-color: #7c3aed; }}
.fb-check input[type=checkbox] {{ accent-color: #7c3aed; width: 20px; height: 20px; cursor: pointer; flex-shrink: 0; }}
.fb-hint {{ font-size: .7rem; color: #4b5563; font-weight: 400; }}
#btn-clear {{
  background: #1e1035; color: #a78bfa; border: 1px solid #4c1d95;
  border-radius: 6px; padding: 7px 14px; font-size: .82rem; cursor: pointer;
  transition: background .15s;
}}
#btn-clear:hover {{ background: #2d1760; }}
.fb-status {{ font-size: .78rem; color: #4b5563; margin-top: 6px; }}

/* ── Content ── */
.wrap {{ max-width: 1440px; margin: 0 auto; padding: 32px 20px; }}
section {{ margin-bottom: 52px; }}
.sec-title {{
  font-size: 1.35rem; font-weight: 800;
  padding: 12px 18px; border-radius: 8px; margin-bottom: 18px;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}}
.sec-label {{ white-space: nowrap; }}
.sec-chips {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.fchip {{
  display: inline-flex; align-items: center;
  font-size: 1rem; font-weight: 700;
  padding: 5px 14px; border-radius: 20px;
  letter-spacing: .3px;
}}
.fchip-query  {{ background: #1c1200; color: #fbbf24; border: 1.5px solid #92400e; }}
.fchip-year   {{ background: #0a1a30; color: #60a5fa; border: 1.5px solid #1e3a5f; }}
.fchip-genre  {{ background: #160d2e; color: #c084fc; border: 1.5px solid #3b1f6e; }}
.fchip-nw     {{ background: #1a0d00; color: #fb923c; border: 1.5px solid #7c2d00; }}
.fchip-lang   {{ background: #001a10; color: #4ade80; border: 1.5px solid #064e24; }}
.fchip-browse {{ background: #0f172a; color: #94a3b8; border: 1.5px solid #1e293b; }}
.sec-count {{
  margin-{side}: auto; font-size: .78rem; font-weight: 400;
  color: #4b5563; background: #111827;
  padding: 2px 10px; border-radius: 20px;
}}
.movie-section .sec-title {{
  background: linear-gradient(135deg, #1a1000, #241600);
  border-{side}: 4px solid #f59e0b; color: #fbbf24;
}}
.tv-section .sec-title {{
  background: linear-gradient(135deg, #001408, #001b0e);
  border-{side}: 4px solid #10b981; color: #34d399;
}}
.soon-badge {{
  display: inline-block; margin-{side}: 8px;
  font-size: .75rem; font-weight: 700;
  background: #0c1f3f; color: #38bdf8;
  border: 1px solid #0369a1; border-radius: 12px;
  padding: 2px 9px; vertical-align: middle;
  letter-spacing: .3px;
}}
.future-card {{ border-color: #0369a1 !important; box-shadow: 0 0 0 1px rgba(56,189,248,.15); }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(720px, 1fr));
  gap: 22px;
}}
.card {{
  border-radius: 14px; padding: 28px;
  transition: transform .15s, box-shadow .15s;
}}
.card:hover {{ transform: translateY(-3px); box-shadow: 0 10px 36px rgba(0,0,0,.45); }}
.movie-card {{
  background: linear-gradient(145deg, #1a1200, #1f1600);
  border: 1px solid #3d2800;
}}
.movie-card:hover {{ border-color: rgba(245,158,11,.4); }}
.tv-card {{
  background: linear-gradient(145deg, #001508, #001b0a);
  border: 1px solid #003d18;
}}
.tv-card:hover {{ border-color: rgba(16,185,129,.35); }}
.desc-match {{ border-style: dashed !important; opacity: .93; }}
.card-top {{ display: flex; gap: 12px; margin-bottom: 10px; align-items: flex-start; }}
.icon {{ font-size: 1.25rem; flex-shrink: 0; margin-top: 2px; }}
.card-main {{ flex: 1; min-width: 0; }}
.card-header {{
  display: flex; justify-content: space-between;
  align-items: flex-start; gap: 8px; margin-bottom: 6px;
}}
.card-title {{ font-size: 1.3rem; font-weight: 700; line-height: 1.35; }}
.movie-card .card-title {{ color: #fbbf24; }}
.tv-card .card-title {{ color: #34d399; }}
.card-date {{ font-size: .82rem; color: #6b7280; white-space: nowrap; margin-top: 3px; flex-shrink: 0; }}
.genres {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }}
.badge {{
  font-size: .75rem; padding: 3px 10px; border-radius: 20px;
  background: #1a2035; color: #a78bfa; border: 1px solid #312e81;
}}
.lang-badge {{
  font-size: .75rem; padding: 3px 10px; border-radius: 20px;
  background: #0d2430; color: #22d3ee; border: 1px solid #0e7490; font-weight: 600;
}}
.overview {{ font-size: 1.15rem; color: #c0c8d8; line-height: 1.8; margin-top: 14px; }}
mark.hl {{
  background: rgba(245,158,11,.22); color: #fbbf24;
  font-weight: 600; border-radius: 3px; padding: 0 2px;
}}
.empty {{ color: #374151; font-style: italic; padding: 24px; text-align: center; }}
footer {{
  text-align: center; padding: 16px;
  color: #1f2937; font-size: .77rem;
  border-top: 1px solid #111827; margin-top: 28px;
}}
@media (max-width: 860px) {{
  .grid {{ grid-template-columns: 1fr; }}
  header h1 {{ font-size: 1.3rem; }}
  .fb-row {{ gap: 8px; }}
}}"""

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{direction}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WatchSearch — {q_display}</title>
<style>{css}</style>
</head>
<body>
<header>
  <h1>🎬 WatchSearch</h1>
  <div class="sub">Results for <strong>{q_display}</strong> &bull; {now}</div>
</header>
{filter_panel}
<div class="wrap">
{movies_sec}
{tv_sec}
</div>
<footer>WatchSearch &mdash; TMDB &mdash; {now}</footer>
{filter_js}
</body>
</html>"""


def _resolve_multi_genre(genre_csv: str, is_movie: bool):
    """Resolve comma-separated genre names to (id_list, pipe_param).

    id_list   — list of int IDs for post-filter checks
    pipe_param — pipe-joined string for TMDB with_genres (OR logic), or None
    """
    if not genre_csv:
        return [], None
    names = [g.strip() for g in genre_csv.split(',') if g.strip()]
    ids = [get_genre_id(n, is_movie=is_movie) for n in names]
    ids = [x for x in ids if x]
    param = '|'.join(str(x) for x in ids) if ids else None
    return ids, param


def run_search(
    query: str,
    year,
    genre_name,
    limit: int,
    movies_only: bool,
    series_only: bool,
    not_watched: bool,
    translate: bool,
    desc_length: int,
    watched_set=None,
    lang_filter=None,  # list of full language names (case-insensitive)
    whole_word: bool = False,
) -> dict:
    """Re-run TMDB search with given parameters. Returns {movies, tvs, timing}."""
    import time as _t
    import datetime as _dt
    import copy as _copy
    if watched_set is None:
        watched_set = set()
    today = _dt.date.today().isoformat()
    timing = {}
    movie_items: list = []
    tv_items: list = []
    query_words = query.lower().split() if query else []

    def _proc_item(result, is_movie: bool):
        """Extract fields from a TMDB result object into a dict (no nw filter — done post-cache)."""
        try:
            if is_movie:
                title = getattr(result, 'title', '') or ''
                raw_date = getattr(result, 'release_date', '') or ''
            else:
                title = getattr(result, 'name', '') or ''
                raw_date = getattr(result, 'first_air_date', '') or ''
            overview = getattr(result, 'overview', '') or ''
            if desc_length and desc_length > 0 and len(overview) > desc_length:
                overview = overview[:desc_length] + '...'
            gmap = movie_genres if is_movie else tv_genres
            genre_names = []
            if hasattr(result, 'genre_ids'):
                genre_names = [gmap.get(g, '') for g in result.genre_ids if g in gmap]
                genre_names = [g for g in genre_names if g]
            lang_code = getattr(result, 'original_language', '') or ''
            lang_name = _LANG_NAMES.get(lang_code, lang_code.upper() if lang_code else '')
            score = _relevance_score(title, overview, query, whole_word=whole_word)
            if query and score == 0:
                return None  # no match in title or description
            return {
                'title': title,        # raw English title
                'title_en': title,     # kept for Hebrew display later
                'date': raw_date[:10] if raw_date else '',
                'year': raw_date[:4] if raw_date else '',
                'genres': genre_names,
                'overview': overview,
                'is_future': bool(raw_date and raw_date[:10] > today),
                'prefix': '🎬' if is_movie else '📺',
                'score': score,
                'lang': lang_code,
                'lang_name': lang_name,
                'tmdb_id': getattr(result, 'id', None),
                'poster_path': result.__dict__.get('poster_path') or getattr(result, 'poster_path', None) or '',
            }
        except Exception:
            return None

    def _combine(primary, secondary, gids, is_movie: bool):
        # gids: list of int IDs; filter if any ID matches (OR logic)
        if gids and query:
            primary   = [r for r in primary   if hasattr(r,'genre_ids') and any(g in r.genre_ids for g in gids)]
            secondary = [r for r in secondary if hasattr(r,'genre_ids') and any(g in r.genre_ids for g in gids)]
        seen: set = set()
        out = []
        for r in list(primary) + list(secondary):
            rid = getattr(r, 'id', None)
            if rid and rid not in seen:
                seen.add(rid)
                out.append(r)
        if limit > 0:
            out = out[:limit]
        return out

    # ── Build browse lang code (ISO) for API-level language filtering ─────────
    _LANG_NAMES_REV = {v.lower(): k for k, v in _LANG_NAMES.items()}
    _browse_lang_code = None
    if lang_filter and not query:
        for lf in lang_filter:
            lfl = lf.lower()
            if lfl in _LANG_NAMES_REV:
                _browse_lang_code = _LANG_NAMES_REV[lfl]
                break
            elif len(lf) <= 3:  # already an ISO code
                _browse_lang_code = lfl
                break

    # ── Search cache check ─────────────────────────────────────────────────────
    _t_start = _t.time()
    _lang_key = tuple(sorted(l.lower() for l in lang_filter)) if lang_filter else ()
    _cache_key = (query or '', year or '', genre_name or '', limit, desc_length, _lang_key)
    _cache_hit = _cache_key in _search_cache
    if _cache_hit:
        cached = _search_cache[_cache_key]
        movie_items = _copy.deepcopy(cached['movies'])
        tv_items    = _copy.deepcopy(cached['tvs'])
        timing['tmdb'] = 0.0

    # ── Movies + TV TMDB fetch (skipped on cache hit) ─────────────────────────
    _t_tmdb = _t.time()
    if not _cache_hit and not series_only:
        t0 = _t.time()
        mgid_list, mgid_param = _resolve_multi_genre(genre_name, is_movie=True)
        if not query:
            primary = browse_by_genre_year(genre_id=mgid_param, year=year, is_movie=True, limit=limit, lang_code=_browse_lang_code)
            secondary = []
        elif year:
            try:
                kw = {"primary_release_year": year}
                if mgid_param:
                    kw["with_genres"] = mgid_param
                yr = _tmdb_discover(is_movie=True, **kw)
                ql = query.lower()
                primary = [r for r in yr if hasattr(r,'title') and r.title and (
                    any(w in r.title.lower() for w in query_words) or ql in r.title.lower()
                    or (r.overview and ql in r.overview.lower()))]
            except Exception:
                primary = []
            reg = movie.search(query)
            seen_ids = {r.id for r in primary if hasattr(r,'id')}
            for r in reg:
                if hasattr(r,'release_date') and r.release_date:
                    try:
                        if int(r.release_date.split('-')[0]) == year and r.id not in seen_ids:
                            primary.append(r)
                    except (ValueError, IndexError):
                        pass
            secondary = search_in_description(query, is_movie=True, limit=limit, year_filter=year, whole_word=whole_word) if query else []
        else:
            primary   = movie.search(query)
            secondary = search_in_description(query, is_movie=True, limit=limit, year_filter=None, whole_word=whole_word) if query else []
        for r in _combine(primary, secondary, mgid_list, True):
            d = _proc_item(r, True)
            if d:
                movie_items.append(d)
        timing['_tmdb_movie'] = round(_t.time() - t0, 2)

    # ── TV (skipped on cache hit) ──────────────────────────────────────────────
    if not _cache_hit and not movies_only:
        t0 = _t.time()
        tgid_list, tgid_param = _resolve_multi_genre(genre_name, is_movie=False)
        if not query:
            primary = browse_by_genre_year(genre_id=tgid_param, year=year, is_movie=False, limit=limit, lang_code=_browse_lang_code)
            secondary = []
        elif year:
            try:
                kw = {"first_air_date_year": year}
                if tgid_param:
                    kw["with_genres"] = tgid_param
                yr = _tmdb_discover(is_movie=False, **kw)
                ql = query.lower()
                primary = [r for r in yr if hasattr(r,'name') and r.name and (
                    any(w in r.name.lower() for w in query_words) or ql in r.name.lower()
                    or (r.overview and ql in r.overview.lower()))]
            except Exception:
                primary = []
            reg = tv.search(query)
            seen_ids = {r.id for r in primary if hasattr(r,'id')}
            for r in reg:
                if hasattr(r,'first_air_date') and r.first_air_date:
                    try:
                        if int(r.first_air_date.split('-')[0]) == year and r.id not in seen_ids:
                            primary.append(r)
                    except (ValueError, IndexError):
                        pass
            secondary = search_in_description(query, is_movie=False, limit=limit, year_filter=year, whole_word=whole_word) if query else []
        else:
            primary   = tv.search(query)
            secondary = search_in_description(query, is_movie=False, limit=limit, year_filter=None, whole_word=whole_word) if query else []
        for r in _combine(primary, secondary, tgid_list, False):
            d = _proc_item(r, False)
            if d:
                tv_items.append(d)
        timing['_tmdb_tv'] = round(_t.time() - t0, 2)

    # ── Store in search cache (raw English, before nw/type/translate) ─────────
    if not _cache_hit:
        _search_cache[_cache_key] = {
            'movies': _copy.deepcopy(movie_items),
            'tvs':    _copy.deepcopy(tv_items),
        }

    # ── Mark is_watched on every item (non-blocking; skipped if data not ready yet) ───
    # For _LazyWatched: use is_ready() to avoid blocking searches while loading.
    # For plain sets: always mark. For empty/None: skip.
    _t_nw = _t.time()
    _ws_ready = bool(watched_set) and (
        not hasattr(watched_set, 'is_ready') or watched_set.is_ready()
    )
    if _ws_ready:
        for item in movie_items:
            item['is_watched'] = item['title'].lower() in watched_set
        for item in tv_items:
            item['is_watched'] = item['title'].lower() in watched_set
    else:
        for item in movie_items:
            item['is_watched'] = False
        for item in tv_items:
            item['is_watched'] = False

    # ── Apply not_watched filter post-cache ───────────────────────────────────
    if not_watched:
        if not _ws_ready and watched_set:
            # User asked for Unwatched filter but data not loaded yet → block once
            for item in movie_items:
                item['is_watched'] = item['title'].lower() in watched_set  # blocks
            for item in tv_items:
                item['is_watched'] = item['title'].lower() in watched_set
        movie_items = [m for m in movie_items if not m['is_watched']]
        tv_items    = [t for t in tv_items    if not t['is_watched']]
    timing['nw'] = round(_t.time() - _t_nw, 3)

    # ── Apply type filter post-cache ──────────────────────────────────────────
    if series_only:
        movie_items = []
    if movies_only:
        tv_items = []

    # ── Apply language filter post-cache ──────────────────────────────────────
    if lang_filter:
        _langs_lower = {l.lower() for l in lang_filter}
        def _lang_match(item):
            lname = item.get('lang_name', '').lower()
            lcode = item.get('lang', '').lower()
            return lname in _langs_lower or lcode in _langs_lower
        movie_items = [m for m in movie_items if _lang_match(m)]
        tv_items    = [t for t in tv_items    if _lang_match(t)]

    # ── Batch translate all items in one HTTP call ───────────────────────────
    if translate:
        t0_tr = _t.time()
        all_items = movie_items + tv_items
        # Build a flat text list: [title, overview, g0, g1, ..., title, overview, ...]
        # Track (item_idx, field) for remapping
        flat_texts: list = []
        mapping: list = []  # (item_index, field_key, genre_index_or_None)
        for idx, item in enumerate(all_items):
            flat_texts.append(item['title_en'])
            mapping.append((idx, 'title', None))
            flat_texts.append(item['overview'])
            mapping.append((idx, 'overview', None))
            for gi, g in enumerate(item['genres']):
                flat_texts.append(g)
                mapping.append((idx, 'genres', gi))

        translated, _tr_cached, _tr_new = translate_batch_he(flat_texts)

        for (idx, field, gi), tr in zip(mapping, translated):
            item = all_items[idx]
            if field == 'title':
                if tr and tr.strip() != item['title_en'].strip():
                    item['title'] = f"{item['title_en']} {{{tr}}}"
                # else: translation same as original (proper noun / failed) — keep as-is
            elif field == 'overview':
                item['overview'] = tr
            elif field == 'genres' and gi is not None:
                item['genres'][gi] = tr

        timing['translate'] = round(_t.time() - t0_tr, 3)
        timing['tr_cached'] = _tr_cached   # strings served from cache
        timing['tr_new']    = _tr_new      # strings fetched from network
    else:
        timing['translate'] = 0.0
        timing['tr_cached'] = 0
        timing['tr_new']    = 0

    # Merge internal tmdb sub-keys into one 'tmdb' key, then clean up
    if not _cache_hit:
        timing['tmdb'] = round(
            timing.pop('_tmdb_movie', 0.0) + timing.pop('_tmdb_tv', 0.0), 3
        )
    timing['total'] = round(_t.time() - _t_start, 3)  # true wall-clock total
    # Sort: relevance desc (then date asc) when query given; date asc when browsing
    if query:
        movie_items.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))
        tv_items.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))
    else:
        movie_items.sort(key=lambda x: x.get('date', '') or '')
        tv_items.sort(key=lambda x: x.get('date', '') or '')
    return {'movies': movie_items, 'tvs': tv_items, 'timing': timing}


def generate_spa_html(init_args, all_genres: list) -> str:
    """Generate the SPA page for interactive server mode."""
    import html as _h
    import datetime as _dt

    today_str = _dt.date.today().isoformat()
    cur_year  = _dt.date.today().year
    iq  = _h.escape(init_args.query or '')
    iyr = str(init_args.year) if init_args.year else ''
    ign = _h.escape(init_args.genre or '')
    ilm = str(getattr(init_args, 'limit', 20))
    idc = str(getattr(init_args, 'desc_length', 0))
    ity = 'movie' if init_args.movies_only else ('tv' if init_args.series_only else 'all')
    inw = 'true' if init_args.not_watched else 'false'
    itr = 'true' if init_args.translate else 'false'

    # Year dropdown: current year → 1874 (oldest TMDB movie)
    _yr_options = '\n'.join(
        f'<option value="{y}"{"  selected" if str(y) == iyr else ""}>{y}</option>'
        for y in range(cur_year, 1873, -1)
    )
    year_opts = '<option value="">Any Year</option>\n' + _yr_options

    # Initial genres (comma-separated from CLI, passed as JS constant for pre-checking)
    init_genres_js = _h.escape(init_args.genre or '')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WatchSearch — Interactive</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:linear-gradient(135deg,#09090f 0%,#0c1220 55%,#09090f 100%);
  color:#dde1ef;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding-bottom:48px}}
header{{background:linear-gradient(90deg,#12002b,#0a1525,#00122b);
  border-bottom:2px solid #7c3aed;padding:14px 28px;position:sticky;top:0;z-index:100}}
header h1{{font-size:1.5rem;color:#a78bfa;font-weight:800}}
#filter-bar{{position:sticky;top:58px;z-index:90;
  background:linear-gradient(90deg,#0d0d20,#0a1020);
  border-bottom:1px solid #2d1f5e;padding:12px 24px 10px;backdrop-filter:blur(12px)}}
.fb-title{{font-size:.7rem;color:#7c3aed;font-weight:700;letter-spacing:1px;
  text-transform:uppercase;margin-bottom:8px}}
.fb-row{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}}
.fb-group{{display:flex;flex-direction:column;gap:3px}}
.fb-group label{{font-size:.72rem;color:#6b7280;font-weight:600}}
.fb-group input,.fb-group select{{
  background:#111827;color:#e2e8f0;border:1px solid #2d3748;
  border-radius:6px;padding:5px 9px;font-size:.84rem;outline:none;min-width:88px}}
.fb-group input:focus,.fb-group select:focus{{border-color:#7c3aed}}
.genre-dd{{position:relative;display:inline-block}}
.genre-btn{{background:#111827;color:#e2e8f0;border:1px solid #2d3748;border-radius:6px;
  padding:5px 9px;font-size:.84rem;min-width:130px;cursor:pointer;text-align:left;
  display:block;width:100%}}
.genre-btn:focus{{border-color:#7c3aed;outline:none}}
.genre-panel{{display:none;position:absolute;top:calc(100% + 4px);left:0;z-index:500;
  background:#0e1422;border:1px solid #3b2a6e;border-radius:8px;padding:6px 4px;
  min-width:180px;max-height:260px;overflow-y:auto;box-shadow:0 8px 24px rgba(0,0,0,.6)}}
.genre-panel label{{display:flex;align-items:center;gap:8px;padding:4px 10px;
  border-radius:4px;cursor:pointer;font-size:.84rem;color:#e2e8f0;white-space:nowrap}}
.genre-panel label:hover{{background:#1a1035}}
.genre-panel input[type=checkbox]{{accent-color:#7c3aed;cursor:pointer;flex-shrink:0}}
.fb-check{{display:flex;align-items:flex-end;padding:0}}
.fb-check label{{
  display:inline-flex;align-items:center;gap:6px;cursor:pointer;
  color:#c4b5fd;font-size:.9rem;font-weight:700;
  background:#1a1035;border:1.5px solid #3b2a6e;
  border-radius:8px;padding:6px 10px;
}}
.fb-check label:hover{{background:#221445;border-color:#7c3aed}}
.fb-check input[type=checkbox]{{accent-color:#7c3aed;width:16px;height:16px;min-width:0;background:none;border:none;padding:0;cursor:pointer;flex-shrink:0}}
#btn-search{{background:#065f46;color:#6ee7b7;border:none;border-radius:6px;
  padding:7px 18px;font-size:.84rem;cursor:pointer;font-weight:700}}
#btn-search:hover{{background:#047857}}
#btn-clear{{background:#4c0519;color:#fca5a5;border:1px solid #7f1d1d;
  border-radius:6px;padding:7px 12px;font-size:.82rem;cursor:pointer;font-weight:700}}
#btn-clear:hover{{background:#7f1d1d}}
.fb-status{{font-size:.75rem;color:#4b5563;margin-top:6px}}
.timing{{font-size:.72rem;color:#374151;margin-top:2px}}
.wrap{{max-width:1440px;margin:0 auto;padding:28px 20px}}
section{{margin-bottom:48px}}
.sec-title{{font-size:1.35rem;font-weight:800;padding:12px 18px;border-radius:8px;
  margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.sec-label{{white-space:nowrap}}
.sec-chips{{display:flex;flex-wrap:wrap;gap:7px;align-items:center}}
.fchip{{display:inline-flex;align-items:center;font-size:.95rem;font-weight:700;
  padding:4px 13px;border-radius:20px}}
.fchip-query{{background:#1c1200;color:#fbbf24;border:1.5px solid #92400e}}
.fchip-year{{background:#0a1a30;color:#60a5fa;border:1.5px solid #1e3a5f}}
.fchip-genre{{background:#160d2e;color:#c084fc;border:1.5px solid #3b1f6e}}
.fchip-nw{{background:#1a0d00;color:#fb923c;border:1.5px solid #7c2d00}}
.fchip-lang{{background:#001a10;color:#4ade80;border:1.5px solid #064e24}}
.fchip-browse{{background:#0f172a;color:#94a3b8;border:1.5px solid #1e293b}}
.sec-count{{margin-left:auto;font-size:.75rem;color:#4b5563;background:#111827;
  padding:2px 9px;border-radius:20px}}
.movie-section .sec-title{{background:linear-gradient(135deg,#1a1000,#241600);
  border-left:4px solid #f59e0b;color:#fbbf24}}
.tv-section .sec-title{{background:linear-gradient(135deg,#001408,#001b0e);
  border-left:4px solid #10b981;color:#34d399}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(680px,1fr));gap:20px}}
.card{{border-radius:14px;padding:24px;transition:transform .15s,box-shadow .15s}}
.card:hover{{transform:translateY(-3px);box-shadow:0 10px 36px rgba(0,0,0,.45)}}
.movie-card{{background:linear-gradient(145deg,#1a1200,#1f1600);border:1px solid #3d2800}}
.movie-card:hover{{border-color:rgba(245,158,11,.4)}}
.tv-card{{background:linear-gradient(145deg,#001508,#001b0a);border:1px solid #003d18}}
.tv-card:hover{{border-color:rgba(16,185,129,.35)}}
.future-card{{border-color:#0369a1!important;box-shadow:0 0 0 1px rgba(56,189,248,.15)}}
.card-top{{display:flex;gap:11px;margin-bottom:9px;align-items:flex-start}}
.icon{{font-size:1.2rem;flex-shrink:0;margin-top:2px}}
.card-main{{flex:1;min-width:0}}
.card-header{{display:flex;justify-content:space-between;align-items:flex-start;
  gap:8px;margin-bottom:5px}}
.card-title{{font-size:1.25rem;font-weight:700;line-height:1.35}}
.movie-card .card-title{{color:#fbbf24}}
.tv-card .card-title{{color:#34d399}}
.card-date{{font-size:.8rem;color:#6b7280;white-space:nowrap;margin-top:3px;flex-shrink:0}}
.soon-badge{{display:inline-block;margin-left:7px;font-size:.72rem;font-weight:700;
  background:#0c1f3f;color:#38bdf8;border:1px solid #0369a1;
  border-radius:12px;padding:2px 8px;vertical-align:middle}}
.genres{{display:flex;flex-wrap:wrap;gap:5px;margin-top:2px}}
.badge{{font-size:.73rem;padding:3px 9px;border-radius:20px;
  background:#1a2035;color:#a78bfa;border:1px solid #312e81}}
.lang-badge{{font-size:.73rem;padding:3px 9px;border-radius:20px;
  background:#0d2430;color:#22d3ee;border:1px solid #0e7490;font-weight:600}}
.watched-badge{{font-size:.73rem;padding:3px 9px;border-radius:20px;
  background:#1a1a0a;color:#facc15;border:1px solid #854d0e;font-weight:600}}
.lang-badges{{display:flex;flex-wrap:wrap;gap:5px;margin-top:3px}}
.overview{{font-size:1.1rem;color:#c0c8d8;line-height:1.75;margin-top:12px}}
.poster-img{{width:60px;height:90px;object-fit:cover;border-radius:6px;flex-shrink:0;margin-right:4px}}
.trailer-btn{{background:#1e0a3c;color:#c084fc;border:1.5px solid #6d28d9;border-radius:6px;
  padding:5px 14px;font-size:.82rem;cursor:pointer;font-weight:700;margin-top:10px;display:inline-block}}
.trailer-btn:hover{{background:#2d1060;border-color:#a78bfa}}
.trailer-btn:disabled{{opacity:.5;cursor:default}}
.trailer-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:2000;
  display:flex;align-items:center;justify-content:center;cursor:pointer}}
.trailer-modal-box{{width:min(88vw,960px);aspect-ratio:16/9;border-radius:14px;overflow:hidden;
  box-shadow:0 0 80px rgba(124,58,237,.6);cursor:default;flex-shrink:0}}
.trailer-modal-iframe{{width:100%;height:100%;border:none;display:block}}
.empty{{color:#374151;font-style:italic;padding:20px;text-align:center}}
#loading{{display:none;text-align:center;padding:40px;color:#4b5563;font-size:1.1rem}}
/* ── RTL (Hebrew) — only results boxes, filter bar stays LTR ── */
#results.rtl{{direction:rtl}}
#results.rtl .movie-section .sec-title{{border-left:none;border-right:4px solid #f59e0b}}
#results.rtl .tv-section .sec-title{{border-left:none;border-right:4px solid #10b981}}
#results.rtl .sec-count{{margin-left:0;margin-right:auto}}
#results.rtl .soon-badge{{margin-left:0;margin-right:7px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><h1>🎬 WatchSearch — Live</h1></header>
<div id="filter-bar">
  <div class="fb-title">🔧 Filters — changes auto-search</div>
  <div class="fb-row">
    <div class="fb-group">
      <label>Query</label>
      <input id="f-query" type="text" placeholder="title or keywords" value="{iq}">
    </div>
    <div class="fb-group fb-check">
      <label id="f-ww-label" style="opacity:.35;pointer-events:none"><input id="f-ww" type="checkbox" disabled> Whole Word</label>
    </div>
    <div class="fb-group">
      <label>Type</label>
      <select id="f-type">
        <option value="all"{"  selected" if ity=="all" else ""}>All</option>
        <option value="movie"{"  selected" if ity=="movie" else ""}>Movies</option>
        <option value="tv"{"  selected" if ity=="tv" else ""}>TV Series</option>
      </select>
    </div>
    <div class="fb-group">
      <label>Year</label>
      <select id="f-year" style="width:110px">
        {year_opts}
      </select>
    </div>
    <div class="fb-group">
      <label>Genre</label>
      <div class="genre-dd" id="genre-dd">
        <button type="button" class="genre-btn" id="genre-btn">Any Genre ▾</button>
        <div class="genre-panel" id="genre-panel"></div>
      </div>
    </div>
    <div class="fb-group">
      <label>Language</label>
      <div class="genre-dd" id="lang-dd">
        <button type="button" class="genre-btn" id="lang-btn">Any Language ▾</button>
        <div class="genre-panel" id="lang-panel"></div>
      </div>
    </div>
    <div class="fb-group">
      <label>Limit</label>
      <input id="f-limit" type="number" min="0" value="{ilm}" style="width:70px">
    </div>
    <div class="fb-group">
      <label>Desc chars</label>
      <input id="f-desc" type="number" min="0" step="100" value="{idc}" style="width:80px">
    </div>
    <div class="fb-group fb-check">
      <label><input id="f-nw" type="checkbox" {"checked" if inw=="true" else ""}> Unwatched</label>
    </div>
    <div class="fb-group fb-check">
      <label><input id="f-translate" type="checkbox" {"checked" if itr=="true" else ""}> Hebrew</label>
    </div>
    <button id="btn-search">Search</button>
    <button id="btn-clear">✕ Clear</button>
  </div>
  <div class="fb-status" id="fb-status">Ready.</div>
  <div class="timing" id="fb-timing"></div>
</div>
<div id="loading">⏳ Searching...</div>
<div class="wrap" id="results">
  <section class="movie-section">
    <div class="sec-title" id="movie-title">
      <span class="sec-label">🎬 Movies</span>
      <div class="sec-chips" id="movie-chips"></div>
      <span class="sec-count" id="count-movie">—</span>
    </div>
    <div class="grid" id="grid-movie"></div>
  </section>
  <section class="tv-section">
    <div class="sec-title" id="tv-title">
      <span class="sec-label">📺 TV Series</span>
      <div class="sec-chips" id="tv-chips"></div>
      <span class="sec-count" id="count-tv">—</span>
    </div>
    <div class="grid" id="grid-tv"></div>
  </section>
</div>
<div id="trailer-overlay" class="trailer-overlay" style="display:none">
  <div class="trailer-modal-box" id="trailer-modal-box">
    <iframe id="trailer-modal-iframe" class="trailer-modal-iframe"
      allowfullscreen allow="autoplay; encrypted-media; fullscreen"></iframe>
  </div>
</div>
<script>
(function(){{
  const TODAY = '{today_str}';
  const INIT_GENRES = '{init_genres_js}'.split(',').map(s => s.trim()).filter(Boolean);
  let debounceTimer = null;

  function gv(id) {{ return document.getElementById(id); }}

  function makeEl(tag, cls, text) {{
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }}

  function buildChips(q, yr, genre, nw, translate, lang) {{
    const chips = [];
    if (q)       chips.push(['fchip fchip-query',  '🔍 ' + q]);
    if (yr)      chips.push(['fchip fchip-year',   '📅 ' + yr]);
    if (genre)   chips.push(['fchip fchip-genre',  '🎭 ' + genre]);
    if (lang)    chips.push(['fchip fchip-lang',   '🌍 ' + lang]);
    if (nw)      chips.push(['fchip fchip-nw',     '👁 Unwatched']);
    if (translate) chips.push(['fchip fchip-lang', '🌐 Hebrew']);
    if (!chips.length) chips.push(['fchip fchip-browse', '✦ Browse All']);
    return chips;
  }}

  function renderChips(containerId, chips) {{
    const c = gv(containerId);
    while (c.firstChild) c.removeChild(c.firstChild);
    chips.forEach(([cls, label]) => c.appendChild(makeEl('span', cls, label)));
  }}

  function buildCard(item, kind) {{
    const isFuture = item.is_future;
    const card = makeEl('div', 'card ' + kind + '-card' + (isFuture ? ' future-card' : ''));
    card.dataset.type = kind;
    card.dataset.year = item.year || '';
    card.dataset.genres = (item.genres || []).join('|').toLowerCase();

    const top = makeEl('div', 'card-top');
    if (item.poster_path) {{
      const poster = document.createElement('img');
      poster.className = 'poster-img';
      poster.src = '/api/image?path=' + encodeURIComponent(item.poster_path);
      poster.alt = item.title || '';
      poster.onerror = function() {{ this.style.display = 'none'; }};
      top.appendChild(poster);
    }}
    const icon = makeEl('span', 'icon', kind === 'movie' ? '🎬' : '📺');
    top.appendChild(icon);

    const main = makeEl('div', 'card-main');
    const hdr = makeEl('div', 'card-header');
    hdr.appendChild(makeEl('span', 'card-title', item.title));

    const dateWrap = makeEl('span', 'card-date', item.date || '');
    if (isFuture) dateWrap.appendChild(makeEl('span', 'soon-badge', '🔜 Coming Soon'));
    hdr.appendChild(dateWrap);

    main.appendChild(hdr);

    const badgeRow = makeEl('div', 'genres');
    if (item.genres && item.genres.length) {{
      item.genres.forEach(g => badgeRow.appendChild(makeEl('span', 'badge', g)));
    }}
    if (item.lang_name || item.lang) {{
      badgeRow.appendChild(makeEl('span', 'lang-badge', item.lang_name || item.lang));
    }}
    if (item.is_watched) {{
      badgeRow.appendChild(makeEl('span', 'watched-badge', '👁 Watched'));
    }}
    if (badgeRow.children.length) main.appendChild(badgeRow);

    top.appendChild(main);
    card.appendChild(top);
    card.appendChild(makeEl('div', 'overview', item.overview || ''));
    if (item.tmdb_id) {{
      const trailerBtn = makeEl('button', 'trailer-btn', '▶ Trailer');
      trailerBtn.addEventListener('click', function() {{
        trailerBtn.disabled = true;
        trailerBtn.textContent = '⏳ Loading…';
        fetch('/api/trailer?id=' + item.tmdb_id + '&type=' + kind)
          .then(r => r.json())
          .then(d => {{
            trailerBtn.disabled = false;
            trailerBtn.textContent = '▶ Trailer';
            if (d.key) {{
              openTrailerModal(d.key);
            }} else {{
              trailerBtn.textContent = '⚠ No trailer';
              trailerBtn.disabled = true;
            }}
          }})
          .catch(() => {{
            trailerBtn.disabled = false;
            trailerBtn.textContent = '⚠ Error';
          }});
      }});
      card.appendChild(trailerBtn);
    }}
    return card;
  }}

  function renderGrid(gridId, items, kind) {{
    const grid = gv(gridId);
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    if (!items || !items.length) {{
      grid.appendChild(makeEl('p', 'empty', 'No results found.'));
    }} else {{
      items.forEach(item => grid.appendChild(buildCard(item, kind)));
    }}
  }}

  function doSearch() {{
    const q       = gv('f-query').value.trim();
    const type    = gv('f-type').value;
    const yr      = gv('f-year').value;
    const genre   = getSelectedGenres();
    const lang    = getSelectedLangs();
    const limit   = gv('f-limit').value || '20';
    const desc    = gv('f-desc').value || '0';
    const nw      = gv('f-nw').checked;
    const transl  = gv('f-translate').checked;
    const ww      = gv('f-ww').checked;

    if (!q && !yr && !genre) {{
      gv('fb-status').textContent = 'Enter a query, year, or genre.';
      return;
    }}

    gv('loading').style.display = 'block';
    gv('results').style.opacity = '0.4';
    gv('fb-status').textContent = 'Searching…';
    gv('fb-timing').textContent = '';

    const chips = buildChips(q, yr, genre, nw, transl, lang);
    renderChips('movie-chips', chips);
    renderChips('tv-chips', chips);

    const params = new URLSearchParams({{
      query: q, year: yr, genre: genre, lang: lang,
      type: type, limit: limit, desc: desc,
      nw: nw ? 'true' : 'false',
      translate: transl ? 'true' : 'false',
      whole_word: ww ? 'true' : 'false'
    }});

    fetch('/api/search?' + params)
      .then(r => r.json())
      .then(data => {{
        gv('loading').style.display = 'none';
        gv('results').style.opacity = '1';
        renderGrid('grid-movie', data.movies, 'movie');
        renderGrid('grid-tv',    data.tvs,    'tv');
        gv('count-movie').textContent = (data.movies ? data.movies.length : 0) + ' results';
        gv('count-tv').textContent    = (data.tvs    ? data.tvs.length    : 0) + ' results';
        const t = data.timing || {{}};
        gv('fb-status').textContent = (data.movies.length + data.tvs.length) + ' results';
        const trCached = t.tr_cached || 0;
        const trNew    = t.tr_new    || 0;
        const trLabel  = (trCached || trNew)
          ? 'Translate: ' + (t.translate||0) + 's (' + trCached + '⚡ ' + trNew + '🌐)'
          : '';
        const nwLabel  = t.nw != null ? '  Unwatched: ' + t.nw + 's' : '';
        gv('fb-timing').textContent =
          (t.tmdb === 0 ? '⚡ cache  ' : '') +
          'TMDB: ' + (t.tmdb||0) + 's  ' +
          trLabel + (trLabel ? '  ' : '') +
          nwLabel +
          'Total: ' + (t.total||0) + 's';
        // Hide sections with no results when type filter active
        const ms = document.querySelector('.movie-section');
        const ts = document.querySelector('.tv-section');
        if (type === 'movie') {{ ts.style.display = 'none'; ms.style.display = ''; }}
        else if (type === 'tv') {{ ms.style.display = 'none'; ts.style.display = ''; }}
        else {{ ms.style.display = ''; ts.style.display = ''; }}
      }})
      .catch(err => {{
        gv('loading').style.display = 'none';
        gv('results').style.opacity = '1';
        gv('fb-status').textContent = 'Error: ' + err;
      }});
  }}

  function applyDirection() {{
    const isHe = gv('f-translate').checked;
    gv('results').classList.toggle('rtl', isHe);
  }}

  function scheduleSearch() {{
    applyDirection();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(doSearch, 650);
  }}

  function clearFilters() {{
    gv('f-query').value = '';
    gv('f-type').value  = 'all';
    gv('f-year').value  = '';
    const _cp = gv('genre-panel');
    if (_cp) Array.from(_cp.querySelectorAll('input[type=checkbox]')).forEach(cb => {{ cb.checked = false; }});
    updateGenreBtn();
    const _lp = gv('lang-panel');
    if (_lp) Array.from(_lp.querySelectorAll('input[type=checkbox]')).forEach(cb => {{ cb.checked = false; }});
    updateLangBtn();
    gv('f-limit').value = '20';
    gv('f-desc').value  = '0';
    gv('f-nw').checked  = false;
    gv('f-translate').checked = false;
    gv('f-ww').checked  = false;
    syncWwState();
    gv('fb-status').textContent = 'Cleared.';
    gv('fb-timing').textContent = '';
  }}

  ['f-type','f-year','f-limit','f-desc','f-nw','f-translate','f-ww']
    .forEach(id => {{
      const el = gv(id);
      if (el) {{ el.addEventListener('change', scheduleSearch); el.addEventListener('input', scheduleSearch); }}
    }});
  function syncWwState() {{
    const hasQuery = gv('f-query').value.trim().length > 0;
    const lbl = gv('f-ww-label');
    const cb  = gv('f-ww');
    lbl.style.opacity        = hasQuery ? '1'    : '0.35';
    lbl.style.pointerEvents  = hasQuery ? ''     : 'none';
    cb.disabled              = !hasQuery;
    if (!hasQuery) cb.checked = false;
  }}

  gv('f-query').addEventListener('input', syncWwState);
  gv('f-query').addEventListener('keydown', e => {{ syncWwState(); if (e.key === 'Enter') doSearch(); else scheduleSearch(); }});
  gv('btn-search').addEventListener('click', doSearch);
  gv('btn-clear').addEventListener('click', clearFilters);

  // ── Genre custom dropdown ──────────────────────────────────────────────────
  function getSelectedGenres() {{
    const panel = gv('genre-panel');
    if (!panel) return '';
    return Array.from(panel.querySelectorAll('input[type=checkbox]:checked'))
      .map(cb => cb.value).join(',');
  }}

  function updateGenreBtn() {{
    const panel = gv('genre-panel');
    const btn   = gv('genre-btn');
    if (!btn) return;
    const checked = panel ? Array.from(panel.querySelectorAll('input[type=checkbox]:checked')) : [];
    if (checked.length === 0)      btn.textContent = 'Any Genre \u25be';
    else if (checked.length === 1) btn.textContent = checked[0].value + ' \u25be';
    else                           btn.textContent = checked.length + ' genres \u25be';
  }}

  gv('genre-btn').addEventListener('click', function(e) {{
    e.stopPropagation();
    const panel = gv('genre-panel');
    const isOpen = panel.style.display === 'block';
    panel.style.display = isOpen ? 'none' : 'block';
  }});

  document.addEventListener('click', function(e) {{
    const dd = gv('genre-dd');
    if (dd && !dd.contains(e.target)) {{
      const panel = gv('genre-panel');
      if (panel) panel.style.display = 'none';
    }}
  }});

  // Fetch genres from server and build checkbox list
  (function loadGenres() {{
    fetch('/api/genres')
      .then(r => r.json())
      .then(genres => {{
        const panel = gv('genre-panel');
        if (!panel) return;
        const prevSelected = getSelectedGenres().split(',').filter(Boolean);
        panel.innerHTML = '';
        genres.forEach(g => {{
          const lbl = document.createElement('label');
          const cb  = document.createElement('input');
          cb.type  = 'checkbox';
          cb.value = g;
          if (prevSelected.includes(g) || INIT_GENRES.includes(g)) cb.checked = true;
          cb.addEventListener('change', () => {{ updateGenreBtn(); scheduleSearch(); }});
          lbl.appendChild(cb);
          lbl.appendChild(document.createTextNode(' ' + g));
          panel.appendChild(lbl);
        }});
        updateGenreBtn();
      }})
      .catch(() => {{}});
  }})();

  // ── Language custom dropdown ───────────────────────────────────────────────
  function getSelectedLangs() {{
    const panel = gv('lang-panel');
    if (!panel) return '';
    return Array.from(panel.querySelectorAll('input[type=checkbox]:checked'))
      .map(cb => cb.value).join(',');
  }}

  function updateLangBtn() {{
    const panel = gv('lang-panel');
    const btn   = gv('lang-btn');
    if (!btn) return;
    const checked = panel ? Array.from(panel.querySelectorAll('input[type=checkbox]:checked')) : [];
    if (checked.length === 0)      btn.textContent = 'Any Language \u25be';
    else if (checked.length === 1) btn.textContent = checked[0].value + ' \u25be';
    else                           btn.textContent = checked.length + ' languages \u25be';
  }}

  gv('lang-btn').addEventListener('click', function(e) {{
    e.stopPropagation();
    const panel = gv('lang-panel');
    const isOpen = panel.style.display === 'block';
    panel.style.display = isOpen ? 'none' : 'block';
  }});

  document.addEventListener('click', function(e) {{
    const dd = gv('lang-dd');
    if (dd && !dd.contains(e.target)) {{
      const panel = gv('lang-panel');
      if (panel) panel.style.display = 'none';
    }}
  }});

  (function loadLanguages() {{
    fetch('/api/languages')
      .then(r => r.json())
      .then(langs => {{
        const panel = gv('lang-panel');
        if (!panel) return;
        panel.innerHTML = '';
        langs.forEach(l => {{
          const lbl = document.createElement('label');
          const cb  = document.createElement('input');
          cb.type  = 'checkbox';
          cb.value = l;
          cb.addEventListener('change', () => {{ updateLangBtn(); scheduleSearch(); }});
          lbl.appendChild(cb);
          lbl.appendChild(document.createTextNode(' ' + l));
          panel.appendChild(lbl);
        }});
        updateLangBtn();
      }})
      .catch(() => {{}});
  }})();

  // ── Trailer modal ─────────────────────────────────────────────────────────
  const _tOverlay = gv('trailer-overlay');
  const _tIframe  = gv('trailer-modal-iframe');
  const _tBox     = gv('trailer-modal-box');

  function openTrailerModal(key) {{
    _tIframe.src = 'https://www.youtube.com/embed/' + key + '?autoplay=1';
    _tOverlay.style.display = 'flex';
  }}
  function closeTrailerModal() {{
    _tOverlay.style.display = 'none';
    _tIframe.src = '';
  }}
  // Click on backdrop closes modal; clicks inside the box do not
  _tOverlay.addEventListener('click', closeTrailerModal);
  _tBox.addEventListener('click', function(e) {{ e.stopPropagation(); }});
  document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeTrailerModal(); }});

  // Apply direction on load, then run initial search if args were provided
  applyDirection();
  if ('{iq}' || '{iyr}' || '{ign}') doSearch();
}})();
</script>
</body>
</html>"""


def run_interactive_server(init_args, watched_set=None) -> None:
    """Start a persistent HTTP server for live filter-driven TMDB search."""
    import http.server
    import socketserver
    import json as _json
    import socket
    import urllib.parse

    _trailer_cache: dict = _load_trailer_file()  # (tmdb_id:media_type) -> youtube_key or None
    _image_cache:   dict = {}                    # poster_path -> (bytes, content_type) — memory only

    if watched_set is None:
        watched_set = set()

    # If genres already loaded use them, otherwise pass empty list — JS will fetch /api/genres
    all_genres = sorted(set(list(movie_genres.values()) + list(tv_genres.values()))) if movie_genres else []
    spa = generate_spa_html(init_args, all_genres).encode('utf-8')

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass  # suppress default logging

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/':
                self._send(200, 'text/html; charset=utf-8', spa)
            elif parsed.path == '/api/search':
                params = urllib.parse.parse_qs(parsed.query)
                def p(k, d=''):
                    return params.get(k, [d])[0]
                q       = p('query')
                yr_str  = p('year')
                yr      = int(yr_str) if yr_str else None
                gn      = p('genre') or None
                lim     = int(p('limit') or 20)
                desc    = int(p('desc') or 0)
                mo      = p('type') == 'movie'
                so      = p('type') == 'tv'
                nw      = p('nw') == 'true'
                transl  = p('translate') == 'true'
                ww      = bool(q) and p('whole_word') == 'true'
                lang_str = p('lang')
                lang_filter = [l.strip() for l in lang_str.split(',') if l.strip()] if lang_str else None
                result  = run_search(
                    query=q, year=yr, genre_name=gn, limit=lim,
                    movies_only=mo, series_only=so, not_watched=nw,
                    translate=transl, desc_length=desc, watched_set=watched_set,
                    lang_filter=lang_filter, whole_word=ww,
                )
                t = result['timing']
                _should_log = t.get('tmdb', 1) != 0.0 or nw  # log TMDB fetches OR unwatched searches
                if _should_log:
                    _tr_info  = f"translate={t.get('translate',0)}s ({t.get('tr_cached',0)}⚡/{t.get('tr_new',0)}🌐)"
                    _nw_flag  = " nw=true" if nw else ""
                    _nw_time  = f" nw={t.get('nw',0)}s" if nw else ""
                    _cache_hit = "⚡cache " if t.get('tmdb') == 0.0 else ""
                    print(f"[search] {_cache_hit}q={q!r} yr={yr} genre={gn} type={p('type')}{_nw_flag} "
                          f"→ {len(result['movies'])}m {len(result['tvs'])}tv "
                          f"tmdb={t.get('tmdb',0)}s {_tr_info}{_nw_time} total={t.get('total',0)}s")
                body = _json.dumps(result, ensure_ascii=False).encode('utf-8')
                self._send(200, 'application/json; charset=utf-8', body)
            elif parsed.path == '/api/genres':
                # Wait up to 5s for background genre loading then return list
                _genres_ready_event.wait(timeout=5)
                all_g = sorted(set(list(movie_genres.values()) + list(tv_genres.values())))
                body = _json.dumps(all_g, ensure_ascii=False).encode('utf-8')
                self._send(200, 'application/json; charset=utf-8', body)
            elif parsed.path == '/api/languages':
                langs = sorted(_LANG_NAMES.values())
                body = _json.dumps(langs, ensure_ascii=False).encode('utf-8')
                self._send(200, 'application/json; charset=utf-8', body)
            elif parsed.path == '/api/clear-cache':
                import shutil
                sc = len(_search_cache);  _search_cache.clear()
                tc = len(_trailer_cache); _trailer_cache.clear()
                ic = len(_image_cache);   _image_cache.clear()
                # wipe disk caches
                for _cf in [_TRANS_CACHE_FILE, _TRAILER_CACHE_FILE, _WATCHED_CACHE_FILE]:
                    try: os.remove(_cf)
                    except OSError: pass
                shutil.rmtree(_IMAGE_CACHE_DIR, ignore_errors=True)
                if hasattr(watched_set, 'refresh'):
                    watched_set.refresh()
                    print(f"[cache] cleared: search={sc} trailer={tc} image={ic} + disk caches + watched refreshing")
                else:
                    print(f"[cache] cleared: search={sc} trailer={tc} image={ic} + disk caches")
                body = _json.dumps({'search': sc, 'trailer': tc, 'image': ic}).encode('utf-8')
                self._send(200, 'application/json; charset=utf-8', body)
            elif parsed.path == '/api/trailer':
                import urllib.request as _ur
                params = urllib.parse.parse_qs(parsed.query)
                tmdb_id = params.get('id', [None])[0]
                media_type = params.get('type', ['movie'])[0]
                _tkey = f"{tmdb_id}:{media_type}"  # string key for JSON-serialisable disk cache
                if _tkey in _trailer_cache:
                    trailer_key = _trailer_cache[_tkey]
                else:
                    api_key = os.getenv('TMDB_API_KEY', '')
                    trailer_key = None
                    if tmdb_id and api_key:
                        try:
                            _url = (f'https://api.themoviedb.org/3/{media_type}/{tmdb_id}'
                                    f'/videos?api_key={api_key}&language=en-US')
                            with _ur.urlopen(_url, timeout=8) as _resp:
                                _vdata = _json.loads(_resp.read())
                            for _v in _vdata.get('results', []):
                                if _v.get('site') == 'YouTube' and _v.get('type') == 'Trailer':
                                    trailer_key = _v['key']
                                    break
                            print(f"[trailer] id={tmdb_id} key={trailer_key}")
                        except Exception as _e:
                            print(f"[trailer] ERROR id={tmdb_id}: {_e}")
                    _trailer_cache[_tkey] = trailer_key
                    _save_trailer_file(_trailer_cache)
                    _auto_clear_if_over_limit()
                body = _json.dumps({'key': trailer_key}).encode('utf-8')
                self._send(200, 'application/json; charset=utf-8', body)
            elif parsed.path == '/api/image':
                import urllib.request as _ur
                params = urllib.parse.parse_qs(parsed.query)
                img_path = params.get('path', [''])[0]
                if img_path:
                    # 1) memory cache
                    if img_path in _image_cache:
                        img_data, img_ct = _image_cache[img_path]
                        self._send(200, img_ct, img_data)
                    else:
                        # 2) disk cache
                        _disk = _get_image_from_disk(img_path)
                        if _disk:
                            img_data, img_ct = _disk
                            _image_cache[img_path] = (img_data, img_ct)
                            self._send(200, img_ct, img_data)
                        else:
                            # 3) fetch from TMDB
                            try:
                                _url = 'https://image.tmdb.org/t/p/w154' + img_path
                                with _ur.urlopen(_url, timeout=8) as _resp:
                                    img_data = _resp.read()
                                    img_ct = _resp.headers.get('Content-Type', 'image/jpeg')
                                _image_cache[img_path] = (img_data, img_ct)
                                _save_image_to_disk(img_path, img_data)
                                _auto_clear_if_over_limit()
                                self._send(200, img_ct, img_data)
                            except Exception:
                                self._send(404, 'text/plain', b'image not found')
                else:
                    self._send(400, 'text/plain', b'missing path')
            else:
                self._send(404, 'text/plain', b'Not found')

        def _send(self, code, ct, body):
            try:
                self.send_response(code)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    # Pick a free port
    with socket.socket() as s:
        s.bind(('0.0.0.0', 0))
        port = s.getsockname()[1]

    srv = ThreadingServer(('0.0.0.0', port), Handler)
    url = f'http://127.0.0.1:{port}/'
    print(f"\n{Colors.GREEN}Interactive server: {url}{Colors.END}")
    print(f"{Colors.CYAN}Ctrl+C to stop{Colors.END}\n")
    subprocess.Popen(['/usr/bin/firefox-nightly', url])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Server stopped.{Colors.END}")
        srv.server_close()


# In interactive mode with no initial input, skip straight to web block
if args.interactive and not args.query and not args.year and not args.genre:
    args.web = True  # ensure web block runs

# Initialize counters for tracking filtered titles
movie_filtered_count = 0
tv_filtered_count = 0

# ── Global performance timing ─────────────────────────────────────────────────
import time as _perf_time
_perf: dict = {}
_perf['start'] = _perf_time.time()
# Capture genre load time measured before _perf was initialized
if not _interactive_blank and '_tmdb_genre_load_secs' in dir():
    _perf['TMDB genre load'] = _tmdb_genre_load_secs  # type: ignore[name-defined]
    # _last stays at start — genre load happened before this block, don't skew subsequent deltas
# unwatched load time recorded after background thread wait (see below)

def _tick(label: str) -> None:
    """Record elapsed time since last _tick (or start) under label."""
    now = _perf_time.time()
    last = _perf.get('_last', _perf['start'])
    _perf[label] = round(now - last, 3)
    _perf['_last'] = now

def _print_perf() -> None:
    """Print timing summary to terminal."""
    total = round(_perf_time.time() - _perf['start'], 3)
    skip = {'start', '_last'}
    rows = [(k, v) for k, v in _perf.items() if k not in skip]
    if not rows:
        return
    print(f"\n{Colors.GRAY}{'─'*40}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}⏱  Timing breakdown:{Colors.END}")
    for label, secs in rows:
        bar = '█' * min(int(secs * 10), 30)
        print(f"  {Colors.YELLOW}{label:<25}{Colors.END} {secs:.3f}s  {Colors.GRAY}{bar}{Colors.END}")
    print(f"  {Colors.BOLD}{'total':<25}{Colors.END} {total:.3f}s")
    print(f"{Colors.GRAY}{'─'*40}{Colors.END}")
# ──────────────────────────────────────────────────────────────────────────────

# Search and display movies if not in series-only mode
if not args.series_only and not (args.interactive and not args.query and not args.year and not args.genre):
    genre_label = f" | Genre: {args.genre}" if args.genre else ""
    year_label = f" | Year: {args.year}" if args.year else ""
    query_label = query if query else "(browse)"
    print(f"\n\U0001f3ac {Colors.BOLD}{Colors.GRAY}Movie Results for:{Colors.END} {Colors.UNDERLINE}{query_label}{Colors.END}{year_label}{genre_label}")
    if args.not_watched:
        print(f"{Colors.CYAN}(showing only unwatched titles){Colors.END}")

    movie_results = []
    movie_genre_id = get_genre_id(args.genre, is_movie=True) if args.genre else None

    if not query:
        # Browse mode: no query, use discover with genre/year
        movie_results = browse_by_genre_year(genre_id=movie_genre_id, year=args.year, is_movie=True, limit=args.limit)
        desc_movie_results = []
    elif args.year:
        try:
            discover_kwargs = {"primary_release_year": args.year}
            if movie_genre_id:
                discover_kwargs["with_genres"] = str(movie_genre_id)
            year_results = _tmdb_discover(is_movie=True, **discover_kwargs)
            query_lower = query.lower()
            query_words = query_lower.split()
            for item in year_results:
                if hasattr(item, 'title') and item.title:
                    title_match = any(word in item.title.lower() for word in query_words) or query_lower in item.title.lower()
                    desc_match = False
                    if hasattr(item, 'overview') and item.overview:
                        desc_match = any(word in item.overview.lower() for word in query_words) or query_lower in item.overview.lower()
                    if title_match or desc_match:
                        movie_results.append(item)
        except Exception as e:
            if DEBUG:
                print(f"Error in year-filtered movie search: {e}")

        regular_results = movie.search(query)
        for item in regular_results:
            if hasattr(item, 'release_date') and item.release_date:
                try:
                    item_year = int(item.release_date.split('-')[0])
                    if item_year == args.year and hasattr(item, 'id'):
                        if not any(r.id == item.id for r in movie_results if hasattr(r, 'id')):
                            movie_results.append(item)
                except (ValueError, IndexError):
                    pass
        desc_movie_results = search_in_description(query, is_movie=True, limit=args.limit, year_filter=args.year)
    else:
        movie_results = movie.search(query)
        desc_movie_results = search_in_description(query, is_movie=True, limit=args.limit, year_filter=args.year)

    # Filter by genre if specified and not already filtered via discover
    if args.genre and movie_genre_id and query:
        movie_results = [r for r in movie_results if hasattr(r, 'genre_ids') and movie_genre_id in r.genre_ids]
        desc_movie_results = [r for r in desc_movie_results if hasattr(r, 'genre_ids') and movie_genre_id in r.genre_ids]

    _tick('movie TMDB search')
    # Combine results and remove duplicates
    movie_combined = []
    movie_ids = set()
    for result in movie_results:
        if hasattr(result, 'id') and result.id not in movie_ids:
            movie_combined.append(result)
            movie_ids.add(result.id)
    for result in desc_movie_results:
        if hasattr(result, 'id') and result.id not in movie_ids:
            movie_combined.append(result)
            movie_ids.add(result.id)

    if DEBUG:
        print(f"Found {len(movie_results)} movie results by title and {len(getattr(locals(), 'desc_movie_results', []))} by description")
        print(f"Total unique movies: {len(movie_combined)}")

    # Wait for background watched-titles load (ran in parallel with TMDB search)
    if args.not_watched and _nw_event is not None and not args.web:
        _nw_t0_wait = _startup_timer.time()
        _nw_event.wait()
        watched_titles_lower = _nw_container[0] if _nw_container else set()
        _nw_load_secs = round(_startup_timer.time() - _nw_t0_wait, 3)
        if _nw_load_secs > 0.001:
            _perf['unwatched wait'] = _nw_load_secs

    # Pass 1: collect all filtered items (no translation yet)
    displayed_count = 0
    _term_movie_raw: list = []
    for i, result in enumerate(movie_combined):
        if displayed_count >= args.limit:
            break
        try:
            title = result.title if hasattr(result, 'title') else "Unknown title"
            if args.not_watched and title.lower() in watched_titles_lower:
                movie_filtered_count += 1
                if DEBUG:
                    print(f"Filtering out watched movie: {title}")
                continue
            displayed_count += 1

            if result.overview:
                if args.desc_length > 0:
                    overview = result.overview[:args.desc_length] + ("..." if len(result.overview) > args.desc_length else "")
                else:
                    overview = result.overview
            else:
                overview = "No overview available"

            release_date = result.release_date if hasattr(result, 'release_date') else "Unknown date"
            raw_overview_web = overview
            query_words = query.lower().split() if query else []

            score = _relevance_score(title, overview, query)
            if query and score == 0:
                if DEBUG:
                    print(f"Skipping movie '{title}' - no match")
                continue

            # Score ≤1 means desc-only match → highlight + desc prefix
            title_prefix = "🔍" if query and score == 1 else "📽️"
            if query and score == 1:
                overview = highlight_search_terms(overview, query, query_words)

            genre_names = []
            if hasattr(result, 'genre_ids'):
                genre_names = [movie_genres.get(g_id, "") for g_id in result.genre_ids if g_id in movie_genres]
                genre_names = [g for g in genre_names if g]

            lang_code = getattr(result, 'original_language', '') or ''
            lang_name = _LANG_NAMES.get(lang_code, lang_code.upper() if lang_code else '')

            # --lang filter
            if args.lang:
                _langs_lower = {l.lower() for l in args.lang}
                if lang_name.lower() not in _langs_lower and lang_code.lower() not in _langs_lower:
                    continue

            if args.web:
                web_movie_items.append({
                    'prefix': title_prefix,
                    'title': title,
                    'title_en': title,
                    'date': release_date,
                    'genres': genre_names,
                    'overview': raw_overview_web,
                    'desc_length': args.desc_length,
                    'query': query,
                    'query_words': query_words,
                    'score': score,
                    'lang': lang_code,
                    'lang_name': lang_name,
                })
            else:
                _term_movie_raw.append({
                    'prefix': title_prefix,
                    'title': title,
                    'genres': genre_names,
                    'overview': overview,
                    'date': release_date,
                    'score': score,
                    'lang': lang_code,
                    'lang_name': lang_name,
                })
        except AttributeError as e:
            if DEBUG:
                print(f"Error processing movie result: {e}")
            continue

    # Sort by relevance score desc (then date) when query given
    if query:
        _term_movie_raw.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))
        web_movie_items.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))

    # Pass 2: parallel translate terminal items (all at once)
    if not args.web and _term_movie_raw:
        if args.translate:
            _parallel_translate_terminal(_term_movie_raw)
        for item in _term_movie_raw:
            if args.translate:
                title_display = f"{item['title']} {{{item.get('title_he', item['title'])}}}"
            else:
                title_display = item['title']
            genre_display = ""
            if item['genres']:
                genre_display = f" {Colors.BOLD}[{Colors.PURPLE}{', '.join(item['genres'])}{Colors.END}{Colors.BOLD}]{Colors.END}"
            lang_display = f" {Colors.CYAN}[{item.get('lang_name', '') or item.get('lang', '')}]{Colors.END}" if item.get('lang') else ""
            print(f"{item['prefix']} {Colors.BOLD}{Colors.YELLOW}{title_display}{Colors.END} ({Colors.CYAN}{item['date']}{Colors.END}){genre_display}{lang_display}: {item['overview']}")

_tick('movie process+translate')
# Search and display TV shows if not in movies-only mode
if not args.movies_only and not (args.interactive and not args.query and not args.year and not args.genre):
    if args.not_watched and movie_filtered_count > 0:
        print(f"\n{Colors.CYAN}Note: {movie_filtered_count} already watched movies were filtered out.{Colors.END}")

    genre_label = f" | Genre: {args.genre}" if args.genre else ""
    year_label = f" | Year: {args.year}" if args.year else ""
    query_label = query if query else "(browse)"
    print(f"\n\U0001f4fa {Colors.BOLD}{Colors.GRAY}TV Series Results for:{Colors.END} {Colors.UNDERLINE}{query_label}{Colors.END}{year_label}{genre_label}")
    if args.not_watched:
        print(f"{Colors.CYAN}(showing only unwatched titles){Colors.END}")

    tv_results = []
    tv_genre_id = get_genre_id(args.genre, is_movie=False) if args.genre else None

    if not query:
        # Browse mode
        tv_results = browse_by_genre_year(genre_id=tv_genre_id, year=args.year, is_movie=False, limit=args.limit)
        desc_tv_results = []
    elif args.year:
        try:
            discover_kwargs = {"first_air_date_year": args.year}
            if tv_genre_id:
                discover_kwargs["with_genres"] = str(tv_genre_id)
            year_results = _tmdb_discover(is_movie=False, **discover_kwargs)
            query_lower = query.lower()
            query_words = query_lower.split()
            for item in year_results:
                if hasattr(item, 'name') and item.name:
                    name_match = any(word in item.name.lower() for word in query_words) or query_lower in item.name.lower()
                    desc_match = False
                    if hasattr(item, 'overview') and item.overview:
                        desc_match = any(word in item.overview.lower() for word in query_words) or query_lower in item.overview.lower()
                    if name_match or desc_match:
                        tv_results.append(item)
        except Exception as e:
            if DEBUG:
                print(f"Error in year-filtered TV search: {e}")

        regular_results = tv.search(query)
        for item in regular_results:
            if hasattr(item, 'first_air_date') and item.first_air_date:
                try:
                    item_year = int(item.first_air_date.split('-')[0])
                    if item_year == args.year and hasattr(item, 'id'):
                        if not any(r.id == item.id for r in tv_results if hasattr(r, 'id')):
                            tv_results.append(item)
                except (ValueError, IndexError):
                    pass
        desc_tv_results = search_in_description(query, is_movie=False, limit=args.limit, year_filter=args.year)
    else:
        tv_results = tv.search(query)
        desc_tv_results = search_in_description(query, is_movie=False, limit=args.limit, year_filter=args.year)

    # Filter by genre if specified and not already filtered via discover
    if args.genre and tv_genre_id and query:
        tv_results = [r for r in tv_results if hasattr(r, 'genre_ids') and tv_genre_id in r.genre_ids]
        desc_tv_results = [r for r in desc_tv_results if hasattr(r, 'genre_ids') and tv_genre_id in r.genre_ids]

    _tick('tv TMDB search')
    # Combine results and remove duplicates
    tv_combined = []
    tv_ids = set()
    for result in tv_results:
        if hasattr(result, 'id') and result.id not in tv_ids:
            tv_combined.append(result)
            tv_ids.add(result.id)
    for result in desc_tv_results:
        if hasattr(result, 'id') and result.id not in tv_ids:
            tv_combined.append(result)
            tv_ids.add(result.id)

    if DEBUG:
        print(f"Found {len(tv_results)} TV results by title and {len(desc_tv_results)} by description")
        print(f"Total unique TV shows: {len(tv_combined)}")

    # Pass 1: collect all filtered items (no translation yet)
    displayed_count = 0
    _term_tv_raw: list = []
    for i, result in enumerate(tv_combined):
        if displayed_count >= args.limit:
            break
        try:
            name = result.name if hasattr(result, 'name') else "Unknown title"
            if args.not_watched and name.lower() in watched_titles_lower:
                tv_filtered_count += 1
                if DEBUG:
                    print(f"Filtering out watched TV show: {name}")
                continue
            displayed_count += 1

            if result.overview:
                if args.desc_length > 0:
                    overview = result.overview[:args.desc_length] + ("..." if len(result.overview) > args.desc_length else "")
                else:
                    overview = result.overview
            else:
                overview = "No overview available"

            first_air_date = result.first_air_date if hasattr(result, 'first_air_date') else "Unknown date"
            raw_overview_web = overview
            query_words = query.lower().split() if query else []

            score = _relevance_score(name, overview, query)
            if query and score == 0:
                if DEBUG:
                    print(f"Skipping TV '{name}' - no match")
                continue

            title_prefix = "🔍" if query and score == 1 else "📺"
            if query and score == 1:
                overview = highlight_search_terms(overview, query, query_words)

            genre_names = []
            if hasattr(result, 'genre_ids'):
                genre_names = [tv_genres.get(g_id, "") for g_id in result.genre_ids if g_id in tv_genres]
                genre_names = [g for g in genre_names if g]

            lang_code = getattr(result, 'original_language', '') or ''
            lang_name = _LANG_NAMES.get(lang_code, lang_code.upper() if lang_code else '')

            # --lang filter
            if args.lang:
                _langs_lower = {l.lower() for l in args.lang}
                if lang_name.lower() not in _langs_lower and lang_code.lower() not in _langs_lower:
                    continue

            if args.web:
                web_tv_items.append({
                    'prefix': title_prefix,
                    'title': name,
                    'title_en': name,
                    'date': first_air_date,
                    'genres': genre_names,
                    'overview': raw_overview_web,
                    'desc_length': args.desc_length,
                    'query': query,
                    'query_words': query_words,
                    'score': score,
                    'lang': lang_code,
                    'lang_name': lang_name,
                })
            else:
                _term_tv_raw.append({
                    'prefix': title_prefix,
                    'title': name,
                    'genres': genre_names,
                    'overview': overview,
                    'date': first_air_date,
                    'score': score,
                    'lang': lang_code,
                    'lang_name': lang_name,
                })
        except AttributeError as e:
            if DEBUG:
                print(f"Error processing TV result: {e}")
            continue

    # Sort by relevance score desc (then date) when query given
    if query:
        _term_tv_raw.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))
        web_tv_items.sort(key=lambda x: (-x.get('score', 1), x.get('date', '') or ''))

    # Pass 2: parallel translate terminal items (all at once)
    if not args.web and _term_tv_raw:
        if args.translate:
            _parallel_translate_terminal(_term_tv_raw)
        for item in _term_tv_raw:
            if args.translate:
                title_display = f"{item['title']} {{{item.get('title_he', item['title'])}}}"
            else:
                title_display = item['title']
            genre_display = ""
            if item['genres']:
                genre_display = f" {Colors.BOLD}[{Colors.PURPLE}{', '.join(item['genres'])}{Colors.END}{Colors.BOLD}]{Colors.END}"
            lang_display = f" {Colors.CYAN}[{item.get('lang_name', '') or item.get('lang', '')}]{Colors.END}" if item.get('lang') else ""
            print(f"{item['prefix']} {Colors.BOLD}{Colors.GREEN}{title_display}{Colors.END} ({Colors.CYAN}{item['date']}{Colors.END}){genre_display}{lang_display}: {item['overview']}")

_tick('tv process+translate')
# Show a summary for TV results when using --not-watched
if args.not_watched and tv_filtered_count > 0:
    print(f"\n{Colors.CYAN}Note: {tv_filtered_count} already watched TV shows were filtered out.{Colors.END}")

# Handle case where no results were found (skip in interactive blank-start mode)
_skip_results_check = args.interactive and not args.query and not args.year and not args.genre
if not _skip_results_check and (not args.series_only and len(movie_combined) == 0) and (not args.movies_only and len(tv_combined) == 0):
    print(f"\n{Colors.RED}No results found for query: '{query}'{Colors.END}")
    
    # Offer some helpful suggestions
    print(f"\n{Colors.YELLOW}Suggestions:{Colors.END}")
    print("- Try using fewer or different keywords")
    print("- Check for typos in your search query")
    if args.year:
        print(f"- Try searching without the year filter (-y {args.year})")
    if args.movies_only:
        print("- Try searching for TV series instead (remove -m flag)")
    if args.series_only:
        print("- Try searching for movies instead (remove -s flag)")
    if args.not_watched:
        print("- Try searching without the not-watched filter (remove -n flag)")
    
    print("\nFor more information, use: python WatchSearch.py --help")
elif not _skip_results_check and args.not_watched and (movie_filtered_count > 0 or tv_filtered_count > 0):
    # Show information about filtered results
    total_filtered = movie_filtered_count + tv_filtered_count
    # print(f"\n{Colors.CYAN}Note: {total_filtered} already watched titles were filtered out.{Colors.END}")
    print(f"{Colors.CYAN}Use the search without -n/--not-watched flag to see all results.{Colors.END}")

# Web mode: generate HTML and open in Firefox
if args.web:
    if args.interactive:
        # Load watched set in background thread so Firefox opens immediately
        import threading as _threading
        _watched_container: list = []
        _watched_ready = _threading.Event()

        def _load_watched():
            # Phase 1: load from disk instantly — app is usable immediately
            ws: set = _load_watched_file()
            _watched_container.append(ws)
            _watched_ready.set()
            # Phase 2: sync from Trakt in background — merge + save to disk
            trakt: set = set()
            if get_all_watched_titles is not None:
                try:
                    trakt = {t.lower() for t in get_all_watched_titles()}
                except Exception:
                    pass
            elif 'watched_titles_lower' in dir():
                trakt = watched_titles_lower  # type: ignore[name-defined]
            if trakt:
                merged = ws | trakt
                _watched_container[0] = merged
                _save_watched_file(merged)

        _threading.Thread(target=_load_watched, daemon=True).start()

        # Pass a proxy set that blocks only if actually needed inside run_search
        class _LazyWatched:
            """Proxy that loads watched set in background; blocks only on first access."""
            def is_ready(self) -> bool:
                return _watched_ready.is_set()
            def refresh(self):
                """Re-fetch watched titles from Trakt in a background thread."""
                _watched_ready.clear()
                _watched_container.clear()
                _threading.Thread(target=_load_watched, daemon=True).start()
            def __bool__(self):
                return get_all_watched_titles is not None
            def __contains__(self, item):
                _watched_ready.wait()
                return item in _watched_container[0]
            def __iter__(self):
                _watched_ready.wait()
                return iter(_watched_container[0])
            def __len__(self):
                _watched_ready.wait()
                return len(_watched_container[0])

        run_interactive_server(args, watched_set=_LazyWatched())  # type: ignore[arg-type]
    else:
        # Static web output — batch-translate web items if -t flag set
        if args.translate and (web_movie_items or web_tv_items):
            _all_web = web_movie_items + web_tv_items
            _flat: list = []
            _map: list = []  # (item_idx, 'title'|'overview'|'genre', genre_idx_or_None)
            for _i, _item in enumerate(_all_web):
                _flat.append(_item.get('title_en', _item.get('title', '')))
                _map.append((_i, 'title', None))
                _flat.append(_item.get('overview', ''))
                _map.append((_i, 'overview', None))
                for _gi, _g in enumerate(_item.get('genres', [])):
                    _flat.append(_g)
                    _map.append((_i, 'genre', _gi))
            _translated_web, _, _ = translate_batch_he(_flat)
            for (_i, _field, _gi), _tr in zip(_map, _translated_web):
                _it = _all_web[_i]
                if _field == 'title':
                    _ten = _it.get('title_en', _it.get('title', ''))
                    _it['title'] = f"{_ten} {{{_tr}}}" if _tr else _ten
                elif _field == 'overview':
                    _it['overview'] = _tr or _it['overview']
                elif _field == 'genre' and _gi is not None:
                    _it['genres'][_gi] = _tr or _it['genres'][_gi]
            _tick('batch translate (web)')

        # Load watched set only if -n flag was used (otherwise skip — saves seconds)
        _watched = set()
        if args.not_watched:
            if get_all_watched_titles is not None:
                try:
                    _watched = {t.lower() for t in get_all_watched_titles()}
                except Exception:
                    pass
            elif 'watched_titles_lower' in dir():
                _watched = watched_titles_lower  # type: ignore[name-defined]
        _tick('load watched set')
        html_content = generate_html(
            web_movie_items, web_tv_items, args, query,
            interactive=False, watched_titles=_watched
        )
        _tick('HTML generation')
        import re as _re
        _parts = ['watchsearch']
        if query:
            _parts.append(_re.sub(r'[^a-z0-9]', '', query.lower().replace(' ', '_'))[:20])
        if args.year:
            _parts.append(str(args.year))
        if args.genre:
            _parts.append(_re.sub(r'[^a-z0-9]', '', args.genre.lower())[:12])
        if args.movies_only:
            _parts.append('movies')
        elif args.series_only:
            _parts.append('tv')
        if args.not_watched:
            _parts.append('unwatched')
        if args.translate:
            _parts.append('he')
        html_filename = '_'.join(_parts) + '.html'
        html_path = os.path.join(os.path.expanduser('~'), 'Downloads', html_filename)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        subprocess.Popen(['/usr/bin/firefox-nightly', html_path])
        print(f"\n{Colors.GREEN}Saved: {html_path}{Colors.END}")

_print_perf()
