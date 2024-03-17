"""A simple set implementation using a text file as storage."""

import logging
from pathlib import Path

from rich.logging import RichHandler


logging.basicConfig(format="%(message)s", handlers=[RichHandler(), ])
log = logging.getLogger()


class SimpleSetInFile:
    """A simple set implementation using a text file as storage."""
    path: Path
    lines: list[str]

    def __init__(self, path: Path) -> None:
        """
        Initializes the SimpleSetInFile object with the given file path.
        Reads the contents of the file and populates the set.

        Parameters:
            path (Path): The file path where the set is stored.
        """
        self.path = path
        self.read()

    def read(self, encoding="UTF-8") -> None:
        """
        Reads the contents of the file and updates the set.

        Parameters:
            encoding (str, optional): The encoding of the file. Defaults to "UTF-8".
        """
        text = self.path.read_text(encoding=encoding).strip()
        self.lines = [line.strip() for line in text.splitlines()]

    def append(self, line: str) -> None:
        """
        Appends a new element to the set if it is not already present.
        Writes the updated set to the file.

        Parameters:
            line: The element to be appended to the set.
        """
        lower_lines = [ll.lower() for ll in self.lines]
        if line.lower() in lower_lines:
            log.info("\"%s\" already in set.", line)
        else:
            log.info("add \"%s\" to the set.", line)
            self.lines.append(line)
            self.write()

    def write(self, encoding="UTF-8") -> None:
        """
        Writes the current set elements to the file.

        Parameters:
            encoding (str, optional): The encoding of the file. Defaults to "UTF-8".
        """
        self.path.write_text("\n".join(self.lines), encoding=encoding)
