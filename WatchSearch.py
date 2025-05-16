#!/usr/bin/env python3
from tmdbv3api import TMDb, Movie, TV, Genre
import sys
import os
import argparse

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

# Configuration - adjust these values to control results
MAX_RESULTS_PER_CATEGORY = 20  # Maximum number of results to show for movies and TV shows
DESCRIPTION_LENGTH = 1000  # Number of characters to show from description (0 for full description)

# Parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Search for movies and TV shows from TMDB API",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("query", nargs="+", help="Search query (title or keywords)")

    parser.add_argument("-m", "--movies-only", 
                        action="store_true", 
                        help="Show only movie results")

    parser.add_argument("-s", "--series-only", 
                        action="store_true", 
                        help="Show only TV series results")

    parser.add_argument("-y", "--year", 
                        type=int, 
                        help="Filter results by specific year")

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
    # Debug options
    parser.add_argument("--debug", 
                        action="store_true", 
                        help="Enable debug output")
    
    args = parser.parse_args()
    
    # Convert query list to string (must be done only once)
    args.query = " ".join(args.query)
                        
    # Apply debug setting
    global DEBUG
    DEBUG = args.debug

    # Check for watched module if --not-watched was specified
    if args.not_watched and get_all_watched_titles is None:
        print(f"{Colors.RED}Error: Cannot use --not-watched flag. watched.py module is not available.{Colors.END}")
        sys.exit(1)
    
    return args

# Get command line arguments
args = parse_arguments()
query = args.query

# Load watched titles if using --not-watched flag
watched_titles = set()
if args.not_watched and get_all_watched_titles is not None:
    try:
        watched_titles = get_all_watched_titles()
        # Convert all titles to lowercase for case-insensitive comparison
        watched_titles_lower = {title.lower() for title in watched_titles}
        if DEBUG:
            print(f"Loaded {len(watched_titles)} watched titles for filtering")
    except Exception as e:
        print(f"{Colors.RED}Error loading watched titles: {e}{Colors.END}")
        print("Continuing without watched filtering")
        args.not_watched = False  # Disable filtering

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
    print(f"Result limit: {args.limit}")
    print(f"Description length: {args.desc_length}")
    
tmdb.language = "en"

movie = Movie()
tv = TV()
genre = Genre()

# Get genre lists for movies and TV shows once to use for lookups
try:
    movie_genres = {g.id: g.name for g in genre.movie_list()}
    tv_genres = {g.id: g.name for g in genre.tv_list()}
    if DEBUG:
        print(f"Loaded {len(movie_genres)} movie genres and {len(tv_genres)} TV genres")
except Exception as e:
    if DEBUG:
        print(f"Error loading genres: {e}")
    movie_genres = {}
    tv_genres = {}

def search_in_description(query, is_movie=True, limit=15, year_filter=None):
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
                    year_results = movie.discover(primary_release_year=year_filter)
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
                    year_results = tv.discover(first_air_date_year=year_filter)
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
                
                # Direct substring match
                direct_match = query_lower in item_overview_lower
                
                # Word-level matching
                words_in_overview = [word.strip('.,!?:;()[]{}"\'-') for word in item_overview_lower.split()]
                word_matches = sum(1 for q_word in query_words if any(q_word in w or w in q_word for w in words_in_overview))
                
                # Match criteria - make it stricter to ensure we get relevant matches
                # For single word queries, we need a direct match or the word must be in the overview
                if len(query_words) == 1:
                    match_found = direct_match or query_lower in item_overview_lower
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

# Initialize counters for tracking filtered titles
movie_filtered_count = 0
tv_filtered_count = 0

# Search and display movies if not in series-only mode
if not args.series_only:
    # Add movie section header
    print(f"\n🎬 {Colors.BOLD}{Colors.GRAY}Movie Results for:{Colors.END} {Colors.UNDERLINE}{query}{Colors.END}")
    if args.not_watched:
        print(f"{Colors.CYAN}(showing only unwatched titles){Colors.END}")
    
    # Apply year filter to direct movie search if specified
    movie_results = []

    if args.year:
        # First try direct search with year filter
        try:
            year_results = movie.discover(primary_release_year=args.year)
            # Filter these results by our search query - ensure it actually contains the query
            query_lower = query.lower()
            query_words = query_lower.split()
            for item in year_results:
                # Check if query is in title
                if hasattr(item, 'title') and item.title:
                    title_match = any(word in item.title.lower() for word in query_words) or query_lower in item.title.lower()
                    
                    # Check if query is in overview
                    desc_match = False
                    if hasattr(item, 'overview') and item.overview:
                        desc_match = any(word in item.overview.lower() for word in query_words) or query_lower in item.overview.lower()
                    
                    # Add only if it matches in title or overview
                    if title_match or desc_match:
                        movie_results.append(item)
        except Exception as e:
            if DEBUG:
                print(f"Error in year-filtered movie search: {e}")
        
        # Also do a regular search and filter by year
        regular_results = movie.search(query)
        for item in regular_results:
            if hasattr(item, 'release_date') and item.release_date:
                try:
                    item_year = int(item.release_date.split('-')[0])
                    if item_year == args.year and hasattr(item, 'id'):
                        # Add if not already in results
                        if not any(r.id == item.id for r in movie_results if hasattr(r, 'id')):
                            movie_results.append(item)
                except (ValueError, IndexError):
                    pass
    else:
        # Regular search without year filter
        movie_results = movie.search(query)

    # Look for movies with the search term in description
    desc_movie_results = []
    # Always search descriptions, even if there are no title matches
    desc_movie_results = search_in_description(query, is_movie=True, limit=args.limit, year_filter=args.year)

    # Combine results and remove duplicates
    movie_combined = []
    movie_ids = set()

    # Add title matches first
    for result in movie_results:
        if hasattr(result, 'id') and result.id not in movie_ids:
            movie_combined.append(result)
            movie_ids.add(result.id)

    # Add description matches
    for result in desc_movie_results:
        if hasattr(result, 'id') and result.id not in movie_ids:
            movie_combined.append(result)
            movie_ids.add(result.id)

    if DEBUG:
        print(f"Found {len(movie_results)} movie results by title and {len(desc_movie_results)} by description")
        print(f"Total unique movies: {len(movie_combined)}")
    
    # Filter out watched titles if not-watched flag is set
    displayed_count = 0
    
    # Display the results
    for i, result in enumerate(movie_combined):
        if displayed_count >= args.limit:
            break
            
        try:
            title = result.title if hasattr(result, 'title') else "Unknown title"
            
            # Skip if already watched and --not-watched flag is set
            if args.not_watched and title.lower() in watched_titles_lower:
                movie_filtered_count += 1
                if DEBUG:
                    print(f"Filtering out watched movie: {title}")
                continue
            
            displayed_count += 1

            # Get the full description or truncate based on settings
            if result.overview:
                if args.desc_length > 0:
                    overview = result.overview[:args.desc_length] + ("..." if len(result.overview) > args.desc_length else "")
                else:
                    overview = result.overview  # No truncation
            else:
                overview = "No overview available"
                
            release_date = result.release_date if hasattr(result, 'release_date') else "Unknown date"
            
            # Highlight if found by description search
            title_prefix = "📽️"
            
            # Check if this is a description match (not in title matches)
            title_lower = result.title.lower() if hasattr(result, 'title') else ""
            query_words = query.lower().split()
            
            # Make sure the result actually contains the query in either title or description
            query_lower = query.lower()
            title_match = False
            desc_match = False
            
            if title_lower:
                title_match = any(word in title_lower for word in query_words)
            
            if overview.lower():
                desc_match = query_lower in overview.lower() or any(word in overview.lower() for word in query_words)
            
            # Skip results that don't match in either title or description
            if not title_match and not desc_match:
                if DEBUG:
                    print(f"Skipping {result.title} - no match for '{query}' in title or description")
                continue
                
            # Consider it a description match if no query words are in the title but they are in description
            is_desc_match = not title_match and desc_match
            
            if is_desc_match:
                title_prefix = "🔍" # Different icon for description matches
                
                # Highlight the matching terms in the overview
                overview = highlight_search_terms(overview, query, query_words)
            
            # Get genre names using the pre-loaded movie_genres dictionary
            genre_names = []
            if hasattr(result, 'genre_ids'):
                genre_names = [movie_genres.get(g_id, "") for g_id in result.genre_ids if g_id in movie_genres]
                genre_names = [g for g in genre_names if g]  # Remove empty genre names
            
            # Format genre display
            genre_display = ""
            if genre_names:
                genre_display = f" {Colors.BOLD}[{Colors.PURPLE}{', '.join(genre_names)}{Colors.END}{Colors.BOLD}]{Colors.END}"
            
            print(f"{title_prefix} {Colors.BOLD}{Colors.YELLOW}{result.title}{Colors.END} ({Colors.CYAN}{release_date}{Colors.END}){genre_display}: {overview}")
        except AttributeError as e:
            if DEBUG:
                print(f"Error processing movie result: {e}")
            continue

# Search and display TV shows if not in movies-only mode
if not args.movies_only:
    # Add a summary line for movie results if using --not-watched
    if args.not_watched and movie_filtered_count > 0:
        print(f"\n{Colors.CYAN}Note: {movie_filtered_count} already watched movies were filtered out.{Colors.END}")
    
    print(f"\n📺 {Colors.BOLD}{Colors.GRAY}TV Series Results for:{Colors.END} {Colors.UNDERLINE}{query}{Colors.END}")
    if args.not_watched:
        print(f"{Colors.CYAN}(showing only unwatched titles){Colors.END}")

    # Apply year filter to direct TV search if specified
    tv_results = []
    if args.year:
        # First try direct search with year filter
        try:
            year_results = tv.discover(first_air_date_year=args.year)
            # Filter these results by our search query - ensure it actually contains the query
            query_lower = query.lower()
            query_words = query_lower.split()
            for item in year_results:
                # Check if query is in name
                if hasattr(item, 'name') and item.name:
                    name_match = any(word in item.name.lower() for word in query_words) or query_lower in item.name.lower()
                    
                    # Check if query is in overview
                    desc_match = False
                    if hasattr(item, 'overview') and item.overview:
                        desc_match = any(word in item.overview.lower() for word in query_words) or query_lower in item.overview.lower()
                    
                    # Add only if it matches in name or overview
                    if name_match or desc_match:
                        tv_results.append(item)
        except Exception as e:
            if DEBUG:
                print(f"Error in year-filtered TV search: {e}")
        
        # Also do a regular search and filter by year
        regular_results = tv.search(query)
        for item in regular_results:
            if hasattr(item, 'first_air_date') and item.first_air_date:
                try:
                    item_year = int(item.first_air_date.split('-')[0])
                    if item_year == args.year and hasattr(item, 'id'):
                        # Add if not already in results
                        if not any(r.id == item.id for r in tv_results if hasattr(r, 'id')):
                            tv_results.append(item)
                except (ValueError, IndexError):
                    pass
    else:
        # Regular search without year filter
        tv_results = tv.search(query)

    # Look for TV shows with the search term in description
    desc_tv_results = []
    # Always search descriptions, even if there are no title matches
    desc_tv_results = search_in_description(query, is_movie=False, limit=args.limit, year_filter=args.year)

    # Combine results and remove duplicates  
    tv_combined = []
    tv_ids = set()

    # Add title matches first
    for result in tv_results:
        if hasattr(result, 'id') and result.id not in tv_ids:
            tv_combined.append(result)
            tv_ids.add(result.id)

    # Add description matches
    for result in desc_tv_results:
        if hasattr(result, 'id') and result.id not in tv_ids:
            tv_combined.append(result)
            tv_ids.add(result.id)

    if DEBUG:
        print(f"Found {len(tv_results)} TV results by title and {len(desc_tv_results)} by description")
        print(f"Total unique TV shows: {len(tv_combined)}")
    
    # Filter out watched titles if not-watched flag is set
    displayed_count = 0
    
    for i, result in enumerate(tv_combined):
        if displayed_count >= args.limit:
            break
            
        try:
            name = result.name if hasattr(result, 'name') else "Unknown title"
            
            # Skip if already watched and --not-watched flag is set
            if args.not_watched and name.lower() in watched_titles_lower:
                tv_filtered_count += 1
                if DEBUG:
                    print(f"Filtering out watched TV show: {name}")
                continue
                
            displayed_count += 1
            
            # Get the full description or truncate based on settings
            if result.overview:
                if args.desc_length > 0:
                    overview = result.overview[:args.desc_length] + ("..." if len(result.overview) > args.desc_length else "")
                else:
                    overview = result.overview  # No truncation
            else:
                overview = "No overview available"
                
            first_air_date = result.first_air_date if hasattr(result, 'first_air_date') else "Unknown date"
            
            # Highlight if found by description search
            title_prefix = "📺"
            
            # Check if this is a description match (not in title matches)
            title_lower = result.name.lower() if hasattr(result, 'name') else ""
            query_words = query.lower().split()
            
            # Make sure the result actually contains the query in either title or description
            query_lower = query.lower()
            title_match = False
            desc_match = False
            
            if title_lower:
                title_match = any(word in title_lower for word in query_words)
            
            if overview.lower():
                desc_match = query_lower in overview.lower() or any(word in overview.lower() for word in query_words)
            
            # Skip results that don't match in either title or description
            if not title_match and not desc_match:
                if DEBUG:
                    print(f"Skipping {result.name} - no match for '{query}' in title or description")
                continue
                
            # Consider it a description match if no query words are in the title but they are in description
            is_desc_match = not title_match and desc_match
            
            if is_desc_match:
                title_prefix = "🔍" # Different icon for description matches
                
                # Highlight the matching terms in the overview
                overview = highlight_search_terms(overview, query, query_words)
                
            # Get genre names using the pre-loaded tv_genres dictionary
            genre_names = []
            if hasattr(result, 'genre_ids'):
                genre_names = [tv_genres.get(g_id, "") for g_id in result.genre_ids if g_id in tv_genres]
                genre_names = [g for g in genre_names if g]  # Remove empty genre names
            
            # Format genre display
            genre_display = ""
            if genre_names:
                genre_display = f" {Colors.BOLD}[{Colors.PURPLE}{', '.join(genre_names)}{Colors.END}{Colors.BOLD}]{Colors.END}"
                
            print(f"{title_prefix} {Colors.BOLD}{Colors.GREEN}{result.name}{Colors.END} ({Colors.CYAN}{first_air_date}{Colors.END}){genre_display}: {overview}")
        except AttributeError as e:
            if DEBUG:
                print(f"Error processing TV result: {e}")
            continue

# Show a summary for TV results when using --not-watched
    if args.not_watched and tv_filtered_count > 0:
        print(f"\n{Colors.CYAN}Note: {tv_filtered_count} already watched TV shows were filtered out.{Colors.END}")

# Handle case where no results were found
if (not args.series_only and len(movie_combined) == 0) and (not args.movies_only and len(tv_combined) == 0):
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
elif args.not_watched and (movie_filtered_count > 0 or tv_filtered_count > 0):
    # Show information about filtered results
    total_filtered = movie_filtered_count + tv_filtered_count
    # print(f"\n{Colors.CYAN}Note: {total_filtered} already watched titles were filtered out.{Colors.END}")
    print(f"{Colors.CYAN}Use the search without -n/--not-watched flag to see all results.{Colors.END}")
