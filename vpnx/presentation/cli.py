"""CLI argument parsing and routing."""

import argparse
from typing import List, Optional

from vpnx.application.commands import (
    Command,
    ConnectAllCommand,
    ConnectCommand,
    DownCommand,
    ListCommand,
    SetupCommand,
)
from vpnx.domain.value_objects import VPNType
from vpnx.infrastructure.app_config import AppConfig

VERSION = "2.0.0"


class CLI:
    """Command line interface parser."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="vpnx", description="VPN client")
        parser.add_argument("-v", "--version", action="version", version=VERSION)

        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("setup", help="Configure VPN client")
        sub.add_parser("list", help="List configured VPNs")

        # Connect to single VPN by name
        connect = sub.add_parser("connect", help="Connect to a VPN")
        connect.add_argument("vpn", help="VPN name (e.g., ext, int, prod)")

        # Connect to all configured VPNs
        sub.add_parser("all", help="Connect to all VPNs in sequence")

        # Manually run the configured down script for a VPN
        down = sub.add_parser(
            "down",
            help="Run the configured down script for a VPN (does not stop OpenVPN)",
        )
        down.add_argument("vpn", help="VPN name (e.g., ext, int, prod)")
        down.add_argument(
            "--dev",
            help="Tunnel interface to pass to the script (default: utun0)",
        )

        return parser

    def parse(self, args: list = None) -> Optional[Command]:
        """Parse arguments and return a Command or None."""
        parsed = self.parser.parse_args(args)

        if not parsed.cmd:
            self.parser.print_help()
            return None

        return self._create_command(parsed)

    def _create_command(self, parsed) -> Optional[Command]:
        """Create appropriate command from parsed args."""
        if parsed.cmd == "setup":
            return SetupCommand()
        if parsed.cmd == "list":
            return ListCommand()
        if parsed.cmd == "all":
            vpn_types = self._get_all_vpn_types()
            return ConnectAllCommand(vpn_types)
        if parsed.cmd == "connect":
            return ConnectCommand(VPNType(parsed.vpn))
        if parsed.cmd == "down":
            return DownCommand(VPNType(parsed.vpn), dev=parsed.dev)
        return None

    def _get_all_vpn_types(self) -> List[VPNType]:
        """Get list of all VPN types from config."""
        if self.config:
            return [VPNType(v.name) for v in self.config.vpns]
        return []
