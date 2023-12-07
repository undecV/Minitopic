"""Search and mark as read for Miniflux."""

from datetime import datetime, timedelta, timezone
from typing import Any
import logging
import re
from pathlib import Path
from copy import deepcopy

from rich import box
from rich.style import Style
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, track
from rich.table import Table
import click
import miniflux

from simple_cache import SimpleCache
from config import base_url, api_key

console = Console(highlight=False)
print = console.print  # pylint: disable=w0622

logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[RichHandler(), ])
log = logging.getLogger()


# Configurations

cache_life = timedelta(days=1)
cache_path = Path(__file__).parent / "cache.pkl"
user_dict_path = Path("./dict/user_dict.txt")


def add_to_user_dict(keyword: str, user_dict_path: Path):
    log.info("Appending keyword \"%s\" to user dict.", keyword)
    if not user_dict_path.exists():
        user_dict_path.parent.mkdir(parents=True, exist_ok=True)
    lines = user_dict_path.read_text(encoding="UTF-8").split('\n')
    keywords = [line.split(" ")[0] for line in lines]
    if keyword in keywords:
        log.info("The keyword is already in the dictionary.")
        return
    with user_dict_path.open("a+", encoding="UTF-8") as fp:
        fp.write(keyword + "\n")
        log.info("The keyword is written in the dictionary.")


client = miniflux.Client(base_url=base_url, api_key=api_key)


def color_datetime(date: datetime, strftime: str = "%Y-%m-%d %H:%M:%S"):
    """
    Formats a datetime object with color-coded text based on its age relative to the current datetime.

    Args:
        date (datetime): The datetime object to be formatted.
        strftime (str, optional): A string representing the desired datetime format
                                  (default is "%Y-%m-%d %H:%M:%S").

    Returns:
        str: A formatted string that includes color-coding based on the age of the datetime:
             - If the datetime is within the last 7 days, it will be colored green.
             - If the datetime is between 7 and 14 days ago, it will be colored yellow.
             - If the datetime is older than 14 days, it will be colored red.

    Example:
        >>> from datetime import datetime
        >>> color_datetime(datetime(2023, 9, 20), "%Y-%m-%d")
        '[green]2023-09-20[/green]'

    Note:
        This function uses the 'datetime' module to calculate the age of the input datetime
        relative to the current datetime in UTC.
    """
    now = datetime.now(timezone.utc)
    colors = ["red", "yellow", "green"]
    delta: timedelta = now - date
    for i, color in enumerate(colors):
        days = (len(colors) - i - 1) * 7
        if delta.days >= days:
            return f"[{color}]{date.strftime(strftime)}[/{color}]"
    return date.strftime(strftime)


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
            progress.update(task, total=fetch_total, completed=fetch_count)
            if fetch_count >= fetch_total:
                break
    return entries


CONTEXT_SETTINGS = {"help_option_names": ["--help", "-h"]}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("keyword")
@click.option(
    "-b", "--batch-size", "fetch_batch_size",
    type=click.IntRange(min=100), default=1000, show_default=True,
    help="The number of entries retrieved each time."
)
@click.option(
    "-d", "--dryrun", "dryrun",
    is_flag=True, default=False, show_default=True, help="Dryrun."
)
@click.option(
    "-f", "--force-fetch", "force_fetch",
    is_flag=True, default=False, show_default=True, help="Force fetching from the API regardless of cache expiration."
)
def cli(keyword: str, fetch_batch_size: int, dryrun: bool, force_fetch: bool):
    """Search and mark as read for Miniflux."""
    log.info("keyword: %s", keyword)
    log.info("fetch_batch_size: %d", fetch_batch_size)
    log.info("dryrun: %r", dryrun)
    log.info("force_fetch: %r", force_fetch)

    entries: Any | None = None
    try:
        cache = SimpleCache(cache_path, cache_life)
        assert isinstance(cache.payload, list), "Bad cache format (data, Type)."
        assert not cache.is_expired(), f"Cache file is expired: {cache.cached_time.isoformat()}."
        entries = cache.payload
    except Exception as exception:
        log.warning("Fail to load from cache: %r.", exception)

    if (not entries) or force_fetch:
        log.debug("Fetch start.")
        entries = fetch_entries(client, "unread", fetch_batch_size)
        log.info("%s entries fetched.", len(entries))
        cache = SimpleCache(cache_path, cache_life)
        cache.write(entries)
        log.info("Cache saved: \"%s\".", cache_path)

    results = []
    formated_results = []

    for entry in track(entries, description="Seatching"):

        if match := re.search(keyword, entry["title"], re.IGNORECASE):
            if entry["status"] in ("read", "removed", ):
                continue
            results.append(entry)
            entry = deepcopy(entry)
            start, end = match.start(), match.end()
            # end = start + len(keyword)
            title = entry["title"]
            entry["title"] = f"[link={entry['url']}]{title[:start]}[red]{title[start:end]}[/red]{title[end:]}[/link]"
            entry["published_at"] = color_datetime(datetime.fromisoformat(entry["published_at"]))
            entry["feed"]["title"] = f"[link={entry['feed']['feed_url']}]{entry['feed']['title']}[/link]"
            formated_results.append(entry)

    if len(results) <= 0:
        print("[b green]No result found.[/b green]")
        return 0

    table = Table(
        title=f"Keyword \"[b][red]{keyword}[/red][/b]\" has {len(results)} result.",
        box=box.HORIZONTALS,
        row_styles=[Style(bgcolor="grey19"), Style(bgcolor="black")]
    )
    table.add_column("ID", justify="right", no_wrap=True)
    table.add_column("Title")
    table.add_column("Feed", justify="left", no_wrap=True)
    table.add_column("Date", justify="right", no_wrap=True)

    for result in formated_results:
        table.add_row(str(result["id"]), result["title"], result["feed"]["title"], result["published_at"], )

    print(table)

    click.confirm("Mark all as read?", default=False, abort=True)

    ids = []
    for result in results:
        ids.append(result["id"])

    if dryrun:
        print(f"Dryrun: mark {len(ids)} entries {ids} as read.")
    else:
        cache = SimpleCache(cache_path, cache_life)
        for result in results:
            result["status"] = "read"
        cache.write(entries)
        log.info("Mark as entry %d as read in the cache.", result["id"])

        if user_dict_path:
            add_to_user_dict(keyword, user_dict_path)
        print(f"Marking {len(ids)} entries {ids} as read.")

        client.update_entries(entry_ids=ids, status="read")
    print("Done.")


if __name__ == '__main__':
    import sys

    if len(sys.argv) == 1:
        cli.main(['--help'])
    else:
        cli.main()
