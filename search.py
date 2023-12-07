"""Advenced keyword search.

- AND: "KW1 KW2"
- OR: "KW1 +KW2"
- NOT: "KW1 -KW2"
"""

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
import click

from simple_cache import SimpleCache


console = Console(highlight=False)
print = console.print  # pylint: disable=w0622


logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[RichHandler(), ])
log = logging.getLogger()


cache_path = Path(__file__).parent / "cache.pkl"


CONTEXT_SETTINGS = {"help_option_names": ["--help", "-h"]}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("keywords", nargs=-1)
def cli(keywords: str):
    """Search and mark as read for Miniflux."""
    log.info("keywords: %r", keywords)

    cache = SimpleCache(cache_path)
    entries = cache.payload

    for entry in entries:
        for keyword in keywords:
            if keyword.startswith("+"):
                pass  # OR
            if keyword.startswith("-"):
                pass  # NOT
            else:
                pass  # AND


if __name__ == '__main__':
    import sys

    if len(sys.argv) == 1:
        cli.main(['--help'])
    else:
        cli.main()
