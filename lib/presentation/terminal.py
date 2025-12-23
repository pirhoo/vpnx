"""Terminal operations."""

import os
import re
import select
import sys
import termios
import tty
from typing import Optional


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

    def enter_alt_screen(self) -> None:
        self.write(f"{self.CSI}?1049h")
        self.flush()

    def leave_alt_screen(self) -> None:
        self.write(f"{self.CSI}?1049l")
        self.flush()

    def color(self, name: str) -> str:
        if not self.use_color:
            return ""
        return f"{self.CSI}0;{self.COLORS.get(name, '0')}m"

    def reset(self) -> str:
        return self.color("reset")

    def _parse_key(self, data: str) -> Optional[str]:
        """Parse key from input data, handling escape sequences."""
        if not data:
            return None

        # Check for Ctrl+C (ETX character)
        if "\x03" in data:
            return "CTRL_C"

        # Check for arrow key escape sequences
        if "\x1b[A" in data:
            return "UP"
        elif "\x1b[B" in data:
            return "DOWN"
        elif "\x1b[C" in data:
            return "RIGHT"
        elif "\x1b[D" in data:
            return "LEFT"

        # Return first character for regular keys
        return data[0]

    def set_raw_input(self) -> None:
        """Set terminal to raw input mode (no echo, no line buffering).

        Call restore_input() when done to restore normal terminal settings.
        """
        fd = sys.stdin.fileno()
        self._saved_settings = termios.tcgetattr(fd)
        new_settings = list(self._saved_settings)
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
        new_settings[6][termios.VMIN] = 0
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new_settings)

    def restore_input(self) -> None:
        """Restore terminal to normal input mode."""
        if hasattr(self, "_saved_settings"):
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSANOW, self._saved_settings)

    def read_key(self, timeout: float = 0.1) -> Optional[str]:
        """Read a single key with timeout. Returns None if no input.

        Returns special strings for arrow keys: 'UP', 'DOWN', 'LEFT', 'RIGHT'.

        Note: For best results in a loop, call set_raw_input() before the loop
        and restore_input() after. Otherwise this method will toggle raw mode
        on each call which can cause brief character echo.
        """
        fd = sys.stdin.fileno()

        # Check if raw mode is already set by checking if we have saved settings
        need_restore = not hasattr(self, "_saved_settings")
        if need_restore:
            self.set_raw_input()

        try:
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if not ready:
                return None

            # Read all available input at once
            data = os.read(fd, 32).decode("utf-8", errors="ignore")
            return self._parse_key(data)
        finally:
            if need_restore:
                self.restore_input()
