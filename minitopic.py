"""Advenced keyword search."""

import re
import logging
from typing import Any
from datetime import datetime, timedelta, timezone

import miniflux
import humanize
import click
from rich.theme import Theme
from rich.table import Table
from rich.style import Style
from rich.progress import Progress
from rich.logging import RichHandler
from rich.console import Console
from rich import box

from config import BASE_URL, API_KEY, CACHE_PATH, CACHE_LIFE, USER_DICT_PATH
from utils.simple_cache import SimpleCache
from utils.wordset import SimpleSetInFile

theme = Theme({
    "keyword_and": "bold red",
    "keyword_or": "bold yellow",
})
console = Console(highlight=False, theme=theme)
print = console.print  # pylint: disable=w0622

logging.basicConfig(format="%(message)s", handlers=[RichHandler(), ])
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def and_or_not_match(
    string: str,
    patterns_and: list[str] | None = None, patterns_or: list[str] | None = None, patterns_not: list[str] | None = None
) -> tuple[bool, list[re.Match | None], list[re.Match | None], list[re.Match | None]]:
    """
    Perform a search on the input string using a combination of AND, OR, and NOT patterns.

    Args:
    - string (str): The input string to be searched.
    - patterns_and (list[str], optional): List of patterns for the AND condition.
      All patterns in this list must match in the input string for a positive result.
    - patterns_or (list[str], optional): List of patterns for the OR condition.
      At least one pattern in this list must match in the input string for a positive result.
    - patterns_not (list[str], optional): List of patterns for the NOT condition.
      None of the patterns in this list should match in the input string for a positive result.

    Returns:
    - tuple[bool, list[re.Match | None], list[re.Match | None], list[re.Match | None]]:
      A tuple containing:
      - bool: True if the input string satisfies all specified conditions, False otherwise.
      - list[re.Match | None]: Matches for patterns in the AND condition.
      - list[re.Match | None]: Matches for patterns in the OR condition.
      - list[re.Match | None]: Matches for patterns in the NOT condition.

    Note:
    - Patterns are case-insensitive.
    - If a list for any condition is empty, that condition is considered satisfied.
    """
    patterns_and = patterns_and or []
    patterns_or = patterns_or or []
    patterns_not = patterns_not or []

    matches_and = [re.search(keyword, string, re.IGNORECASE) for keyword in patterns_and]
    matches_or = [re.search(keyword, string, re.IGNORECASE) for keyword in patterns_or]
    matches_not = [re.search(keyword, string, re.IGNORECASE) for keyword in patterns_not]

    is_match_and: bool = bool(len(matches_and) == 0 or all(matches_and))
    is_match_or: bool = bool(len(matches_or) == 0 or any(matches_or))
    is_match_not: bool = bool(len(matches_not) == 0 or not any(matches_not))

    is_match: bool = bool(is_match_and and is_match_or and is_match_not)

    return is_match, matches_and, matches_or, matches_not


def color_datetime(date: datetime, strftime: str = "%Y-%m-%d %H:%M:%S"):
    """
    Format a datetime object with optional coloring based on its recency.

    Args:
    - date (datetime): The datetime object to be formatted.
    - strftime (str, optional): A string specifying the format of the output.
      If set to "humanize" or "natural", a humanized representation of the
      time difference (e.g., '2 days ago') will be used. Otherwise, a custom
      strftime format can be provided. Default is "%Y-%m-%d %H:%M:%S".

    Returns:
    - str: A formatted string representing the input datetime with optional coloring.

    Note:
    - The coloring is based on the recency of the datetime compared to the current time.
      The more recent the datetime, the greener the color; the older, the redder.

    Example:
    ```python
    >>> from datetime import datetime, timedelta
    >>> now = datetime.now()
    >>> recent_date = now - timedelta(days=2)
    >>> old_date = now - timedelta(days=14)
    >>> print(color_datetime(recent_date))  # Output will be in green
    >>> print(color_datetime(old_date))  # Output will be in red
    >>> print(color_datetime(now, strftime="humanize"))  # Output will be a humanized time difference
    ```

    Dependencies:
    - The function relies on the 'humanize' library for humanized time representations.
      Make sure to install it using: `pip install humanize`
    """
    time_str = ""
    if strftime.lower() in ("humanize", "natural", ):
        time_str = humanize.naturaltime(date)
    else:
        time_str = date.strftime(strftime)
    now = datetime.now(timezone.utc)
    colors = ["red", "yellow", "green"]
    delta: timedelta = now - date
    for i, color in enumerate(colors):
        days = (len(colors) - i - 1) * 7
        if delta.days >= days:
            return f"[{color}]{time_str}[/{color}]"
    return time_str


def fetch_entries(client: miniflux.Client, status: str = "unread", fetch_batch_size: int = 100) -> list[Any]:
    """
    Fetch a list of entries from a client with pagination support.

    Args:
        fetch_batch_size (int, optional): The number of entries to fetch in each batch. Defaults to 100.

    Returns:
        list: A list of fetched entries.

    This function retrieves entries from a client in batches, with the specified batch size.
    It uses pagination to ensure all entries are fetched.

    Example usage:
    >>> entries = fetch_entries(fetch_batch_size=50)
    """
    fetch_count: int = 0
    fetch_total: int = 0
    entries: list = []

    log.debug("Fetching with batch size %s.", fetch_batch_size)
    with Progress() as progress:
        task = progress.add_task("Fetching entries...", total=0, start=False)
        while True:
            response = client.get_entries(
                order="published_at", direction="asc", status=status,
                offset=fetch_count, limit=fetch_batch_size
            )
            fetch_total = response["total"]
            fetched = response["entries"]
            fetch_count += len(fetched)
            entries.extend(fetched)
            progress.start_task(task)
            progress.update(task, total=fetch_total, completed=fetch_count,
                            description=f"{fetch_count} / {fetch_total}")
            if fetch_count >= fetch_total:
                break
    return entries


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("keywords", nargs=-1)
@click.option("-a", "--and", "keywords_and", multiple=True, metavar="AND_KEYWORDS",
              help="Specify keywords for 'AND' search. Results must contain all these keywords.")
@click.option("-r", "--or", "keywords_or", multiple=True, metavar="OR_KEYWORDS",
              help="Specify keywords for 'OR' search. Results can contain any of these keywords.")
@click.option("-n", "--not", "keywords_not", multiple=True, metavar="NOT_KEYWORDS",
              help="Specify keywords for 'NOT' search. Results must not contain any of these keywords.")
@click.option("-f", "--force-fetch", "force_fetch", is_flag=True, default=False, show_default=True,
              metavar="FORCE_FETCH", help="Force fetching from the API regardless of cache expiration.")
@click.option("-b", "--batch-size", "fetch_batch_size", type=click.IntRange(min=100), default=1000, show_default=True,
              metavar="FETCH_BATCH_SIZE", help="The number of entries retrieved each time.")
@click.option("-d", "--dryrun", "dryrun", is_flag=True, default=False, show_default=True,
              metavar="DRYRUN", help="Dryrun.")
def cli(keywords: str, keywords_and: list[str], keywords_or: list[str], keywords_not: list[str],
        force_fetch: bool, fetch_batch_size: int, dryrun: bool) -> None:
    """Search and mark as read for Miniflux."""
    keywords_and = keywords + keywords_and

    log.debug("%20s: %r", "keywords", keywords)
    log.debug("%20s: %r", "keywords_and", keywords_and)
    log.debug("%20s: %r", "keywords_or", keywords_or)
    log.debug("%20s: %r", "keywords_not", keywords_not)
    log.debug("%20s: %d", "fetch_batch_size", fetch_batch_size)
    log.debug("%20s: %r", "dryrun", dryrun)
    log.debug("%20s: %r", "force_fetch", force_fetch)

    entries: Any | None = None
    client = miniflux.Client(base_url=BASE_URL, api_key=API_KEY)

    # Fetch and cacheing.
    try:
        cache = SimpleCache(CACHE_PATH, CACHE_LIFE)
        assert isinstance(cache.payload, list), "Bad cache format (data, Type)."
        assert not cache.is_expired(), f"Cache file is expired: {cache.cached_time.isoformat()}."
        entries = cache.payload
    except Exception as exception:  # pylint: disable=w0718
        log.warning("Fail to load from cache: %r.", exception)

    if (not entries) or force_fetch:
        log.debug("Fetch start.")
        entries = fetch_entries(client, "unread", fetch_batch_size)
        log.info("%s entries fetched.", len(entries))
        cache = SimpleCache(CACHE_PATH, CACHE_LIFE)
        cache.write(entries)
        log.info("Cache saved: \"%s\".", CACHE_PATH)

    # Search
    results = []
    table = Table(box=box.HORIZONTALS, row_styles=[Style(bgcolor="grey19"), Style(bgcolor="black")])
    table.add_column("ID", justify="right", no_wrap=True)
    table.add_column("Title")
    table.add_column("Feed", justify="left", no_wrap=True)
    table.add_column("Date", justify="right", no_wrap=True)

    for entry in entries:
        title = entry["title"]

        if entry["status"] in ("read", "removed", ):
            continue

        is_match, matches_and, matches_or, _ = \
            and_or_not_match(title, keywords_and, keywords_or, keywords_not)

        if not is_match:
            continue

        # log.debug("Matches: {AND: %r, OR: %r, NOT: %r}", matches_and, matches_or, matches_not)
        results.append(entry)

        # Decorate table
        matches_and_start = []
        matches_and_end = []
        matches_or_start = []
        matches_or_end = []

        for match in [match for match in matches_and if match]:
            matches_and_start.append(match.start())
            matches_and_end.append(match.end())
        for match in [match for match in matches_or if match]:
            matches_or_start.append(match.start())
            matches_or_end.append(match.end())
        formated_title = ""
        for idx, char in enumerate(title):
            match idx:
                case idx if idx in matches_and_start:
                    formated_title += "[keyword_and]"
                case idx if idx in matches_and_end:
                    formated_title += "[/keyword_and]"
                case idx if idx in matches_or_start:
                    formated_title += "[keyword_or]"
                case idx if idx in matches_or_end:
                    formated_title += "[/keyword_or]"
                case _:
                    pass
            formated_title += char

        title = f"[link={entry['url']}]{formated_title}[/link]"
        enrty_id = str(entry["id"])
        feed = f"[link={entry['feed']['feed_url']}]{entry['feed']['title']}[/link]"
        published_at = color_datetime(datetime.fromisoformat(entry["published_at"]), "humanize")

        table.add_row(enrty_id, title, feed, published_at)

    if len(results) <= 0:
        print("[b green]No result found.[/b green]")
        return 0

    # end for entry in entries
    table.title = f"Find {len(results)} result(s)."
    print(table)
    click.confirm("Mark all as read?", default=False, abort=True)

    user_dict = SimpleSetInFile(USER_DICT_PATH)

    ids = []
    for result in results:
        ids.append(result["id"])

    if dryrun:
        print(f"[red]Dryrun[/red]: mark {len(ids)} entries {ids} as read.")
    else:
        cache = SimpleCache(CACHE_PATH, CACHE_LIFE)
        for result in results:
            result["status"] = "read"
        cache.write(entries)
        log.info("Mark as entry %d as read in the cache.", result["id"])

        words: list[str] = keywords_and + keywords_or
        for word in words:
            user_dict.append(word)

        print(f"Marking {len(ids)} entries {ids} as read.")
        client.update_entries(entry_ids=ids, status="read")
    print("Done.")


if __name__ == '__main__':
    import sys

    if len(sys.argv) == 1:
        cli.main(['--help'])
    else:
        cli.main()
