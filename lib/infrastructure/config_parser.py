"""OpenVPN configuration file parser."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ManagementConfig:
    """Management interface configuration from .ovpn file."""

    enabled: bool
    host: str = ""
    port: int = 0


class OpenVPNConfigParser:
    """Parse and modify OpenVPN configuration files."""

    MANAGEMENT_RE = re.compile(r"^\s*management\s+(\S+)\s+(\d+)", re.MULTILINE)

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def get_management_config(self) -> ManagementConfig:
        """Parse config for 'management <host> <port>' directive."""
        content = self._read_config()
        match = self.MANAGEMENT_RE.search(content)
        if match:
            return ManagementConfig(
                enabled=True,
                host=match.group(1),
                port=int(match.group(2)),
            )
        return ManagementConfig(enabled=False)

    def has_management_directive(self) -> bool:
        """Check if management directive exists."""
        return self.get_management_config().enabled

    def append_management_directive(self, host: str, port: int) -> None:
        """Append management directive to config file."""
        content = self._read_config()
        if not content.endswith("\n"):
            content += "\n"
        content += f"management {host} {port}\n"
        self.config_path.write_text(content)

    def _read_config(self) -> str:
        """Read config file content."""
        return self.config_path.read_text()
