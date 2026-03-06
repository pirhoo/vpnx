#!/usr/bin/env python3
"""VPN Client - Composition Root."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from application import (
    ConnectAllCommand,
    ConnectCommand,
    ListCommand,
    SetupCommand,
)
from application.handlers import (
    ConnectAllHandler,
    ConnectHandler,
    SetupHandler,
)
from domain import VPNService
from infrastructure import (
    CommandRunner,
    FileVPNRepository,
    OpenVPNProcessManager,
    PassPasswordStore,
)
from infrastructure.app_config import AppConfig
from infrastructure.xdg import XDGPaths
from presentation import CLI, TUI, ConsoleDisplay


class Application:
    """Main application - wires dependencies and routes commands."""

    REQUIRED_COMMANDS = ["openvpn", "gpg"]

    def __init__(self):
        self.runner = CommandRunner()
        self.display = ConsoleDisplay()

        # XDG paths
        self.xdg = XDGPaths.default()

        # Load config if exists
        self.config: Optional[AppConfig] = None
        if self.xdg.config_file.exists():
            try:
                self.config = AppConfig.load(self.xdg.config_file)
            except Exception as e:
                self.display.error(f"Error loading config: {e}")

        # Initialize services if config exists
        self.store: Optional[PassPasswordStore] = None
        self.vpn_service: Optional[VPNService] = None

        if self.config:
            self._init_services()

        # Presentation
        self.cli = CLI(self.config)
        self.tui = TUI()

    def _init_services(self) -> None:
        """Initialize services from loaded config."""
        # Build config_paths mapping from VPN configs
        config_paths = {vpn.name: vpn.config_path for vpn in self.config.vpns}

        # Get VPNs that need up/down scripts
        up_script_vpns = [v.name for v in self.config.vpns if v.needs_up_script]
        down_script_vpns = [v.name for v in self.config.vpns if v.needs_down_script]

        def resolve_script(global_path, vpns):
            path = global_path or next((v for v in vpns if v), None)
            return path if path and path.exists() else None

        up_script = resolve_script(
            self.config.up_script,
            (v.up_script for v in self.config.vpns),
        )
        down_script = resolve_script(
            self.config.down_script,
            (v.down_script for v in self.config.vpns),
        )

        # Infrastructure with config_paths
        self.repository = FileVPNRepository(config_paths=config_paths)
        self.process_manager = OpenVPNProcessManager(
            self.runner,
            up_script=up_script,
            down_script=down_script,
            config_paths=config_paths,
        )

        # Password store (might not be initialized)
        self.store = PassPasswordStore(self.config.credentials_path)

        # Domain service
        self.vpn_service = VPNService(
            self.repository, self.process_manager, up_script_vpns, down_script_vpns
        )

    def check_dependencies(self) -> bool:
        """Check if required commands are available."""
        missing = [c for c in self.REQUIRED_COMMANDS if not self.runner.exists(c)]
        if missing:
            self.display.error(f"Error: Missing: {', '.join(missing)}")
            return False
        return True

    def check_setup(self) -> bool:
        """Check if setup has been completed."""
        if not self.config:
            self.display.error("No configuration found. Run 'vpn setup' first.")
            return False
        if not self.config.vpns:
            self.display.error("No VPNs configured. Run 'vpn setup' to add VPNs.")
            return False
        return True

    def check_vpn_running(self) -> bool:
        """Check if OpenVPN is already running."""
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
        """Run the application."""
        command = self.cli.parse(args)
        if command is None:
            return 0

        # Setup doesn't need dependencies or config
        if isinstance(command, SetupCommand):
            handler = SetupHandler(self.xdg, self.runner, self.display, self.store)
            result = handler.handle(command)
            # Reload config after setup
            if result and self.xdg.config_file.exists():
                self.config = AppConfig.load(self.xdg.config_file)
                self._init_services()
            return 0 if result else 1

        # Check dependencies for all other commands
        if not self.check_dependencies():
            return 1

        # List shows configured VPNs
        if isinstance(command, ListCommand):
            if not self.config or not self.config.vpns:
                self.display.print("No VPNs configured. Run 'vpn setup' to add VPNs.")
                return 0
            self.display.print("Configured VPNs:")
            for vpn in self.config.vpns:
                self.display.print(
                    f"  {vpn.name} - {vpn.display_name} ({vpn.config_path})"
                )
            return 0

        # Connection commands need setup
        if not self.check_setup():
            return 1

        # Validate sudo and check for running VPN
        subprocess.run(["sudo", "-v"], check=True)
        if not self.check_vpn_running():
            return 0

        # Get username from config (may be empty - handlers will prompt)
        username = self.config.username if self.config else ""

        if isinstance(command, ConnectCommand):
            # Get config_dir from VPN config for management interface setup
            vpn_config = self.config.get_vpn(command.vpn_type.name)
            if not vpn_config:
                self.display.error(f"Unknown VPN: {command.vpn_type.name}")
                return 1
            config_dir = vpn_config.config_path.parent

            handler = ConnectHandler(
                self.vpn_service,
                self.store,
                username,
                self.tui,
                self.display,
                config_dir,
                vpn_config.needs_2fa,
            )
            return 0 if handler.handle(command) else 1

        if isinstance(command, ConnectAllCommand):
            # Build config paths and 2FA requirements mapping for each VPN
            config_paths = {}
            needs_2fa = {}
            for vpn_type in command.vpn_types:
                vpn_config = self.config.get_vpn(vpn_type.name)
                if vpn_config:
                    config_paths[vpn_type.name] = vpn_config.config_path
                    needs_2fa[vpn_type.name] = vpn_config.needs_2fa

            handler = ConnectAllHandler(
                self.vpn_service,
                self.store,
                username,
                self.tui,
                self.display,
                config_paths,
                command.vpn_types,
                needs_2fa,
            )
            return 0 if handler.handle(command) else 1

        return 1


def main():
    app = Application()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
