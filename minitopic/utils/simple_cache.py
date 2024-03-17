import pickle
import logging
from typing import Any
from pathlib import Path
from datetime import timedelta, datetime

from rich.logging import RichHandler


logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(), ])
log = logging.getLogger(__name__)


class SimpleCache:
    """
    Simple cache implementation that stores data to a file with optional expiration.

    Attributes:
    - lifetime (timedelta | None): The duration for which the cache remains valid.
      If None, the cache is considered to have an indefinite lifetime.
    - path (Path): The path of the cache file.
    - payload (Any): The payload of the cache file.
    - cached_time (datetime): The timestamp indicating when the cache was last updated.

    Methods:
    - __init__(self, cache_path: Path, cache_lifetime: timedelta | None = None) -> None:
      Initializes the SimpleCache object with the specified cache path and optional lifetime.
      Reads the cache file if it exists.

    - exists(self) -> bool:
      Returns True if the cache file exists, False otherwise.

    - write(self, payload: Any) -> None:
      Writes the provided payload to the cache file. Creates the cache file and directory if they
      don't exist. Updates the cached_time attribute.

    - read(self) -> None:
      Reads the cache file and updates the cached_time and payload attributes.

    - is_expired(self, time: datetime = datetime.now()) -> bool:
      Returns True if the cache has expired based on the specified lifetime, False otherwise.
      If lifetime is None, always returns False (indicating an indefinite lifetime).
    """

    lifetime: timedelta | None
    """The duration for which the cache remains valid.
    If None, the cache is considered to have an indefinite lifetime."""
    path: Path
    """The path of the cache file."""
    payload: Any
    """The payload of the cache file."""
    cached_time: datetime
    """The payload of the cache file."""

    def __init__(self, cache_path: Path, cache_lifetime: timedelta | None = None) -> None:
        """
        Initializes the SimpleCache object.

        Parameters:
        - cache_path (Path): The path to the cache file.
        - cache_lifetime (timedelta | None): The duration for which the cache remains valid.
          If None, the cache is considered to have an indefinite lifetime.
        """
        self.path = cache_path
        self.lifetime = cache_lifetime
        self.read()

    def exists(self) -> bool:
        """Returns True if the cache file exists, False otherwise."""
        return self.path.exists()

    def write(self, payload: Any) -> None:
        """
        Writes the provided payload to the cache file.

        Parameters:
        - payload (Any): The data to be stored in the cache.
        """
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        cached_data = {"cached_time": datetime.now(), "data": payload}
        pickle.dump(cached_data, self.path.open("wb"))
        self.read()

    def read(self) -> None:
        """
        Reads the cache file. Creates an empty cache file if it doesn't exist.
        """
        if not self.path.exists():
            self.write(None)
        try:
            cached_data = pickle.load(self.path.open("rb"))
            assert isinstance(cached_data, dict), "Bad cache data (cache_data, Type)."
            cached_time = cached_data["cached_time"]
            assert isinstance(cached_time, datetime), "Bad cache data (cached_time, Type)."
            self.cached_time = cached_time
            self.payload = cached_data["data"]
        except Exception as exception:
            log.warning("Fail to load from cache: %r.", exception)
            self.write(None)

    def is_expired(self, time: datetime = datetime.now()) -> bool:
        """
        Returns True if the cache has expired based on the specified lifetime, False otherwise.
        If lifetime is None, always returns False (indicating an indefinite lifetime).

        Parameters:
        - time (datetime): The reference time for checking expiration.
          Defaults to the current time.
        """
        if not self.lifetime:
            return False
        return self.cached_time < time - self.lifetime


if __name__ == "__main__":
    # Example useage:
    cache = SimpleCache(Path("./example_cache.pkl"), timedelta(seconds=1))
    print(f"Payload: \"{cache.payload}\"")
    print(f"Expired: {cache.is_expired()}")
    cache.write("example_cache")
    print(f"Payload: \"{cache.payload}\"")
    print(f"Expired: {cache.is_expired()}")
