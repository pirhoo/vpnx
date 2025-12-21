"""Process execution utilities."""

import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CommandResult:
    """Result of a command execution."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


class CommandRunner:
    """Execute shell commands with proper error handling."""

    DEFAULT_TIMEOUT = 5

    def run(
        self, cmd: List[str], timeout: Optional[int] = None, text: bool = True
    ) -> CommandResult:
        """Run command and return result."""
        timeout = timeout or self.DEFAULT_TIMEOUT
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=text, timeout=timeout
            )
            stdout = (
                result.stdout
                if text
                else result.stdout.decode("utf-8", errors="replace")
            )
            stderr = (
                result.stderr
                if text
                else result.stderr.decode("utf-8", errors="replace")
            )
            return CommandResult(result.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            return CommandResult(1, "", "Command timed out")
        except FileNotFoundError:
            return CommandResult(127, "", f"Command not found: {cmd[0]}")

    def run_sudo(
        self, cmd: List[str], timeout: Optional[int] = None, text: bool = True
    ) -> CommandResult:
        """Run command with sudo."""
        return self.run(["sudo"] + cmd, timeout, text)

    def exists(self, command: str) -> bool:
        """Check if command exists in PATH."""
        return self.run(["which", command]).success

    def start_background(
        self, cmd: List[str], stdout_file: str, stdin: Optional[int] = None
    ) -> None:
        """Start a background process."""
        with open(stdout_file, "w") as out:
            subprocess.Popen(
                cmd,
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=stdin or subprocess.DEVNULL,
            )
