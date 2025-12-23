"""Log file reading utilities."""

import os
from typing import List, Optional

from .process import CommandRunner


class LogReader:
    """Read log files with fallback to sudo."""

    def __init__(self, runner: Optional[CommandRunner] = None):
        self.runner = runner or CommandRunner()

    def read_tail(
        self, filepath: str, max_lines: int, offset: int = 0
    ) -> List[str]:
        """Read last N lines from a log file, with optional scroll offset.

        Args:
            filepath: Path to the log file
            max_lines: Number of lines to return
            offset: Number of lines to skip from the end (for scrolling)
        """
        if not filepath or not os.path.exists(filepath):
            return []

        # Read more lines if we need to offset
        lines_to_read = max_lines + offset
        result = self.runner.run(["tail", "-n", str(lines_to_read), filepath])
        if not result.success:
            result = self.runner.run_sudo(["tail", "-n", str(lines_to_read), filepath])

        if not result.success:
            return []

        lines = [line.replace("\r", "") for line in result.stdout.split("\n")]
        lines = lines[:-1] if lines and not lines[-1] else lines

        # Apply offset: skip the last 'offset' lines
        if offset > 0 and len(lines) > offset:
            lines = lines[: len(lines) - offset]

        # Return only the last max_lines
        return lines[-max_lines:] if len(lines) > max_lines else lines
