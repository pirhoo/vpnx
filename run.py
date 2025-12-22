#!/usr/bin/env python3
"""ICIJ VPN Client - Composition Root."""

import subprocess
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from domain import VPNService
from infrastructure import (
    CommandRunner,
    FileVPNRepository,
    OpenVPNProcessManager,
    PassPasswordStore,
)
from presentation import CLI, TUI, ConsoleDisplay
from application import SetupCommand, ListCommand, ConnectCommand, ConnectBothCommand
from application.handlers import (
    SetupHandler,
    ListHandler,
    ConnectHandler,
    ConnectBothHandler,
)


class Application:
    """Main application - wires dependencies and routes commands."""

    REQUIRED_COMMANDS = ["openvpn", "pass", "gpg"]

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.runner = CommandRunner()
        self.display = ConsoleDisplay()

        # Infrastructure
        self.repository = FileVPNRepository(base_path / "certificates")
        self.process_manager = OpenVPNProcessManager(
            self.runner, base_path / "certificates", base_path / "scripts" / "up.sh"
        )
        self.store = PassPasswordStore(base_path / "credentials")

        # Domain service
        self.vpn_service = VPNService(self.repository, self.process_manager)

        # Presentation
        self.cli = CLI()
        self.tui = TUI()

    def _load_username(self) -> str:
        f = self.base_path / ".username"
        if f.exists():
            return f.read_text().strip()
        import os

        return os.environ.get("ICIJ_USERNAME", "")

    def check_dependencies(self) -> bool:
        missing = [c for c in self.REQUIRED_COMMANDS if not self.runner.exists(c)]
        if missing:
            self.display.error(f"Error: Missing: {', '.join(missing)}")
            return False
        return True

    def check_setup(self) -> bool:
        if not self._load_username():
            self.display.error("Error: Run 'setup' first")
            return False
        if not self.store.is_initialized():
            self.display.error("Error: Password store not initialized")
            return False
        return True

    def check_vpn_running(self) -> bool:
        result = self.runner.run_sudo(["pgrep", "openvpn"])
        if not result.success:
            return True
        self.display.print("OpenVPN already running")
        response = self.display.input("Kill? [y/N] ").strip().lower()
        if response == "y":
            self.runner.run_sudo(["pkill", "openvpn"])
            import time

            time.sleep(1)
            return True
        return False

    def run(self, args: list = None) -> int:
        command = self.cli.parse(args)
        if command is None:
            return 0

        # Setup doesn't need dependencies
        if isinstance(command, SetupCommand):
            handler = SetupHandler(
                self.store, self.runner, self.base_path, self.display
            )
            return 0 if handler.handle(command) else 1

        # Check dependencies for all other commands
        if not self.check_dependencies():
            return 1

        # List doesn't need setup
        if isinstance(command, ListCommand):
            handler = ListHandler(self.vpn_service, self.display)
            return 0 if handler.handle(command) else 1

        # Connection commands need setup
        if not self.check_setup():
            return 1

        # Validate sudo and check for running VPN
        subprocess.run(["sudo", "-v"], check=True)
        if not self.check_vpn_running():
            return 0

        username = self._load_username()

        if isinstance(command, ConnectCommand):
            handler = ConnectHandler(
                self.vpn_service, self.store, username, self.base_path, self.display
            )
            return 0 if handler.handle(command) else 1

        if isinstance(command, ConnectBothCommand):
            handler = ConnectBothHandler(
                self.vpn_service,
                self.store,
                username,
                self.tui,
                self.display,
                self.base_path / "certificates",
            )
            return 0 if handler.handle(command) else 1

        return 1


def main():
    base_path = Path(__file__).parent.resolve()
    app = Application(base_path)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
