"""Log file reading utilities."""

import os
from typing import List, Optional

from .process import CommandRunner


class LogReader:
    """Read log files with fallback to sudo."""

    def __init__(self, runner: Optional[CommandRunner] = None):
        self.runner = runner or CommandRunner()

    def read_tail(self, filepath: str, max_lines: int) -> List[str]:
        """Read last N lines from a log file."""
        if not filepath or not os.path.exists(filepath):
            return []

        result = self.runner.run(["tail", "-n", str(max_lines), filepath])
        if not result.success:
            result = self.runner.run_sudo(["tail", "-n", str(max_lines), filepath])

        if not result.success:
            return []

        lines = [line.replace("\r", "") for line in result.stdout.split("\n")]
        return lines[:-1] if lines and not lines[-1] else lines
