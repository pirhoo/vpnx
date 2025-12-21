"""Console display for simple output."""

import sys


class ConsoleDisplay:
    """Simple console display implementation."""

    def print(self, message: str) -> None:
        print(message)

    def input(self, prompt: str) -> str:
        return input(prompt)

    def error(self, message: str) -> None:
        print(message, file=sys.stderr)
