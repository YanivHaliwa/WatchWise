# WatchWise

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/YanivHaliwa/WatchWise)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/YanivHaliwa/WatchWise)

A CLI tool to search for movies and TV shows with optional filtering based on your watch history. Integrates with TMDb for media information and Trakt.tv for watch history tracking.

## Features

- 🔍 **Search Movies and TV Shows**: Find content by title or keywords
- 🏠 **Browse Latest**: No query needed — launches with the latest releases by default
- 📺 **Detailed Information**: View release dates, genres, descriptions, and scores
- 🎬 **Filter by Type**: Movies only or TV shows only
- ⌛ **Filter by Year**: Find content from a specific release year
- 🎭 **Filter by Genre**: Browse or search by one or multiple genres (query optional)
- 🌍 **Filter by Language**: Show only content in specific original languages
- ✅ **Watch History Integration**: Filter out content you've already watched
- 🔜 **Coming Soon Control**: Toggle to show or hide upcoming unreleased titles (hidden by default)
- 🔎 **Description Search**: Find media that matches keywords in descriptions
- ⭐ **Rating & Trending Scores**: Each card shows IMDb-style vote average and TMDB popularity score
- 🗂️ **Sort Bar**: Sort results by Latest / Top Rated / Trending / Name / Language — click again to reverse
- 🏷️ **Genre & Language Badges**: Visual display of genres and original language per result
- 🌐 **Hebrew Translation**: Translate titles, descriptions, and genres to Hebrew via `deep_translator` with persistent disk cache
- ⚡ **Smart Caching**: Four cache layers — persistent translation, trailer, and image caches on disk + in-memory TMDB search cache per session
- 🖥️ **Web View** (`-w`): Display results as a static styled dark-theme HTML page opened in Firefox
- 🚀 **Interactive Mode** (`-i`): Full in-browser live server — no `-w` needed, `-i` implies it
- 🖼️ **Poster Images**: Movie/show cover art displayed inside each result card
- 🎬 **YouTube Trailer Modal**: Watch trailers without leaving the page — fullscreen overlay, ESC or click-outside to close
- 🛡️ **1 GB Cache Size Guard**: Disk caches auto-cleared if combined size exceeds 1 GB
- 📊 **Relevance Scoring**: Results ranked by how closely they match your query


## Screenshots

![WatchWise Demo](screenshots/demo.gif)


## Installation

### Prerequisites

- Python 3.6+
- [TMDb API Key](https://www.themoviedb.org/settings/api)
- [Trakt.tv API Access](https://trakt.tv/oauth/applications) (optional, for watch history)
- `jq` (required for `getTrakt.sh`): `apt install jq`

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/YanivHaliwa/WatchWise.git
   cd WatchWise
   ```
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
3. Set up your TMDb API Key:

   ```bash
   export TMDB_API_KEY="your_tmdb_api_key"
   ```
4. (Optional) Set up Trakt.tv integration:

   ```bash
   export TRAKT_CLIENT_ID="your_trakt_client_id"
   export TRAKT_CLIENT_SECRET="your_trakt_client_secret"
   ./getTrakt.sh
   ```

   The script will prompt you to authorize the app, then **automatically save the tokens to `~/.zshrc`** and export them to the current shell. No manual export needed.

## Usage

### Search for Movies and TV Shows

Basic search for both movies and TV shows:

```bash
python WatchSearch.py "The Matrix"
```

Search for movies only:

```bash
python WatchSearch.py -m "The Matrix"
```

Search for TV shows only:

```bash
python WatchSearch.py -s "Breaking Bad"
```

Filter by year:

```bash
python WatchSearch.py -y 2022 "Top Gun"
```

Filter by genre (query is optional — browse without a search term):

```bash
python WatchSearch.py -g Action "Marvel"
python WatchSearch.py -g Action Comedy -y 2023   # browse by genre + year, no query needed
```

Filter by original language:

```bash
python WatchSearch.py --lang Korean
python WatchSearch.py --lang Korean Japanese "thriller"
```

Filter out already watched content:

```bash
python WatchSearch.py -n "Marvel"
```

Limit number of results:

```bash
python WatchSearch.py -l 5 "Star Wars"
```

Control description length:

```bash
python WatchSearch.py -d 200 "Inception"  # Show 200 characters
python WatchSearch.py -d 0 "Inception"    # Show full descriptions
```

Translate results to Hebrew:

```bash
python WatchSearch.py -t "Inception"
```

Open results in a static styled web page:

```bash
python WatchSearch.py -w "Inception"
```

Launch the live interactive server:

```bash
python WatchSearch.py -i              # browse latest releases (no query needed)
python WatchSearch.py -i "Inception"  # start with a query pre-filled
```

> **Note**: `-i` no longer requires `-w`. It implies web mode automatically.

Clear all persistent caches (translation, trailer, images, watched):

```bash
python WatchSearch.py --clear-cache
```

Enable debug output:

```bash
python WatchSearch.py --debug "Matrix"
```

### Interactive Mode (`-i`)

The interactive server opens in Firefox and provides a live filter panel that re-searches automatically as you change options:

| Control | Description |
|---------|-------------|
| **Query** | Title or keyword search |
| **Type** | All / Movies / TV Series |
| **Year** | Filter by release year |
| **Genre** | Multi-select genre dropdown |
| **Language** | Multi-select language dropdown |
| **Limit** | Max results per section (default 20) |
| **Desc chars** | Characters of description to show |
| **Unwatched** | Hide titles you've already watched |
| **Hebrew** | Translate results to Hebrew |
| **Soon** | Show upcoming unreleased titles (off by default — limit is always filled from released titles) |

**Sort bar** (always visible, sticky):

| Button | ↑ | ↓ |
|--------|---|---|
| 📅 Latest | Newest first | Oldest first |
| ⭐ Top Rated | Highest rating first | Lowest first |
| 🔥 Trending | Most popular first | Least popular first |
| 🔤 Name | A → Z (English title) | Z → A |
| 🌐 Language | English first, then A–Z | Reversed |

Each result card shows:
- Poster image, title, release date
- Genre and language badges
- ⭐ Rating score and 🔥 Trending score
- ▶ Trailer button (opens YouTube in a fullscreen overlay)

### Check Watch History

Show all watched movies and TV shows:

```bash
python watched.py -a
```

Check if a specific title has been watched:

```bash
python watched.py -q "Breaking Bad"
```

Enable debug output:

```bash
python watched.py -d
```

## API Keys and Configuration

The application uses environment variables for configuration:

### Required Environment Variables

- `TMDB_API_KEY`: Your TMDb API key (required for movie/show search)

### Optional Environment Variables

- `TRAKT_CLIENT_ID`: Your Trakt.tv client ID (required for watch history)
- `TRAKT_CLIENT_SECRET`: Your Trakt.tv client secret (required for token generation)
- `TRAKT_ACCESS_TOKEN`: Your Trakt.tv access token (auto-saved by `getTrakt.sh`)
- `TRAKT_REFRESH_TOKEN`: Generated by `getTrakt.sh` (for future token refresh)

### Obtaining API Keys

#### TMDb API Key

1. Create an account on [TMDb](https://www.themoviedb.org/)
2. Go to your account settings
3. Select the API section
4. Request an API key for developer use

#### Trakt.tv API Access

1. Create an account on [Trakt.tv](https://trakt.tv)
2. Go to [Settings > Your API Applications](https://trakt.tv/oauth/applications)
3. Create a new application to get your Client ID and Client Secret
4. Set `TRAKT_CLIENT_ID` and `TRAKT_CLIENT_SECRET`, then run `./getTrakt.sh`
5. The script handles the full device-code OAuth flow and saves tokens to `~/.zshrc` automatically

## Caching

WatchWise uses four cache layers to keep things fast:

### Translation Cache (`.trans_cache.json`)

- Loaded automatically at startup
- Auto-saved to disk on exit and after every batch translate
- Parallel batch translation via `deep_translator` (`GoogleTranslator`) — up to 10 concurrent threads
- Already-cached strings are served instantly with zero network calls
- Cache survives across sessions — you never re-translate the same text twice

### Watched Titles Cache (`.watched_cache.json`)

Two-phase load for instant startup:

- **Phase 1**: Loads from `.watched_cache.json` instantly on startup — watched badges appear immediately
- **Phase 2**: Trakt sync runs in a background thread, merges new titles, saves back to disk

Force a full refresh:

```bash
python watched.py -r
```

### Trailer Cache (`.trailer_cache.json`)

- Maps TMDB ID → YouTube trailer key
- Persists across restarts — no re-fetching for movies already seen
- Populated on demand when you click ▶ Trailer

### Image Cache (`.image_cache/`)

- MD5-named files, approximately 15 KB each
- Three-tier lookup: memory → disk → TMDB network
- Populated on demand when interactive mode loads poster images

### TMDB Search Cache (In-Memory)

- Keyed by query, year, genre, limit, and description length
- Repeat searches with the same parameters hit the cache instantly
- Especially useful in interactive mode where filters change frequently

### Cache Size Limit

All four disk caches share a **1 GB combined size limit**. When reached, all disk caches are auto-cleared. Manual clear:

```bash
python WatchSearch.py --clear-cache
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Created by [Yaniv Haliwa](https://github.com/YanivHaliwa) for educational purposes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
