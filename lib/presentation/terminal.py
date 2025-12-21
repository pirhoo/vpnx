"""Terminal operations."""

import os
import re
import sys


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(s: str) -> str:
    """Remove ANSI escape codes from string."""
    return ANSI_RE.sub("", s)


def visible_len(s: str) -> int:
    """Get visible length of string (excluding ANSI codes)."""
    return len(strip_ansi(s))


class Terminal:
    """Low-level terminal operations."""

    CSI = "\033["
    COLORS = {
        "green": "32",
        "red": "31",
        "cyan": "36",
        "yellow": "33",
        "gray": "90",
        "dim": "2",
        "bold": "1",
        "reset": "0",
    }

    def __init__(self):
        self.use_color = os.environ.get("NO_COLOR") is None

    @property
    def width(self) -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    @property
    def height(self) -> int:
        try:
            return os.get_terminal_size().lines
        except OSError:
            return 24

    def write(self, text: str) -> None:
        sys.stdout.write(text)

    def flush(self) -> None:
        sys.stdout.flush()

    def home(self) -> str:
        return f"{self.CSI}H"

    def clear_line(self) -> str:
        return f"{self.CSI}K"

    def clear(self) -> None:
        self.write(f"{self.CSI}2J{self.CSI}H")

    def move_to(self, row: int, col: int) -> None:
        self.write(f"{self.CSI}{row};{col}H")

    def hide_cursor(self) -> None:
        self.write(f"{self.CSI}?25l")
        self.flush()

    def show_cursor(self) -> None:
        self.write(f"{self.CSI}?25h")
        self.flush()

    def color(self, name: str) -> str:
        if not self.use_color:
            return ""
        return f"{self.CSI}0;{self.COLORS.get(name, '0')}m"

    def reset(self) -> str:
        return self.color("reset")
