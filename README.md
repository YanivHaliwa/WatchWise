# WatchWise

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/YanivHaliwa/WatchWise)
[![deepwiki](https://img.shields.io/badge/Ask_DeepWiki-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjE2IiBoZWlnaHQ9IjE2IiByeD0iMiIgZmlsbD0iI2ZmZiIvPgo8dGV4dCB4PSI4IiB5PSIxMSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IkFyaWFsLCBIZWx2ZXRpY2EsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iNyIgZm9udC13ZWlnaHQ9IjcwMCIgZmlsbD0iIzAwMCI+RFc8L3RleHQ+Cjwvc3ZnPgo%3D&logoColor=ffffff)](https://deepwiki.com/YanivHaliwa/WatchWise)

A set of CLI tools to search for movies and TV shows with optional filtering based on your watch history. Integrates with TMDb for media information and Trakt.tv for watch history tracking.

## Features

- 🔍 **Search Movies and TV Shows**: Find content by title or keywords
- 📺 **Detailed Information**: View release dates, genres, and descriptions
- 🎬 **Filter by Type**: Search for movies only or TV shows only
- ⌛ **Filter by Year**: Find content from a specific release year
- ✅ **Watch History Integration**: Filter out content you've already watched
- 🔎 **Description Search**: Find media that matches keywords in descriptions
- 🎭 **Genre Highlighting**: Visual display of genres for better categorization

## Installation

### Prerequisites

- Python 3.6+
- [TMDb API Key](https://www.themoviedb.org/settings/api)
- [Trakt.tv API Access](https://trakt.tv/oauth/applications) (optional, for watch history)

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

   Outputs:

   ```bash
   TRAKT_ACCESS_TOKEN="xyz"   
   TRAKT_REFRESH_TOKEN="xyz"   
   ```

   set up your TRAKT TOKEN:

   ```bash
   export TRAKT_ACCESS_TOKEN="your_trakt_access_token"
   ```

   Follow the instructions to authorize the application and set the required environment variables.

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

Enable debug output:

```bash
python WatchSearch.py --debug "Matrix"
```

screenshots:

![Movie Search Demo](screenshots/filter-watched-result-desc.png "filter number of result and description and not watched")
![Movie Search Demo](screenshots/filter-result-and-desc.png "filter number of result and description")
![Movie Search Demo](screenshots/search-5-result.png "filter number of result")

### Check Watch History

Show all watched movies and TV shows:

```bash
python watched.py -a
```

Check if a specific title has been watched:

```bash
python watched.py -q "Breaking Bad"
```

## API Keys and Configuration

The application uses environment variables for configuration:

### Required Environment Variables

- `TMDB_API_KEY`: Your TMDb API key (required for movie/show search)
- `TRAKT_CLIENT_ID`: Your Trakt.tv client ID (required for watch history)
- `TRAKT_CLIENT_SECRET`: Your Trakt.tv client secret (required for token generation)
- `TRAKT_ACCESS_TOKEN`: Your Trakt.tv access token (required for watch history)

### Optional Environment Variables

- `TRAKT_REFRESH_TOKEN`: Generated when running getTrakt.sh (for future token refresh)

### Obtaining API Keys

#### TMDb API Key

1. Create an account on [TMDb](https://www.themoviedb.org/)
2. Go to your account settings
3. Select the API section
4. Request an API key for developer use

#### Trakt.tv API Access

1. Create an account on [Trakt.tv](https://trakt.tv)
2. Go to [Settings &gt; Your API Applications](https://trakt.tv/oauth/applications)
3. Create a new application to get your Client ID and Client Secret
4. Run `./getTrakt.sh` and follow the instructions to generate your access token

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Created by [Yaniv Haliwa](https://github.com/YanivHaliwa) for educational purposes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
