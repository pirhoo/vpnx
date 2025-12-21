"""CLI argument parsing and routing."""

import argparse
from typing import Optional

from domain.value_objects import VPNType
from application.commands import (
    Command,
    SetupCommand,
    ListCommand,
    ConnectCommand,
    ConnectBothCommand,
)


VERSION = "1.0.0"


class CLI:
    """Command line interface parser."""

    def __init__(self):
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="vpn", description="ICIJ VPN client")
        parser.add_argument("-v", "--version", action="version", version=VERSION)

        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("setup", help="Configure credentials")
        sub.add_parser("list", help="List available VPNs")
        sub.add_parser("ext", help="Connect to EXT VPN")
        sub.add_parser("int", help="Connect to INT VPN")
        sub.add_parser("both", help="Connect to both VPNs (fullscreen)")

        connect = sub.add_parser("connect", help="Connect to specific VPN")
        connect.add_argument("vpn", help="VPN name")

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
        if parsed.cmd == "both":
            return ConnectBothCommand()
        if parsed.cmd == "ext":
            return ConnectCommand(VPNType("EXT"))
        if parsed.cmd == "int":
            return ConnectCommand(VPNType("INT"))
        if parsed.cmd == "connect":
            return ConnectCommand(VPNType(parsed.vpn))
        return None
