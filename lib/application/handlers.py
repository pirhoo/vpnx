"""Command handlers - execute use cases."""

import os
import signal
import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Protocol

from domain import VPNType, VPNState, Status, Credentials, ConnectionResult
from domain.services import VPNService, CredentialStore
from infrastructure.process import CommandRunner
from infrastructure.config_parser import OpenVPNConfigParser
from infrastructure.port_allocator import PortAllocator
from infrastructure.management import ManagementClient, ManagementState
from infrastructure.xdg import XDGPaths
from infrastructure.app_config import AppConfig, VPNConfig
from application.commands import (
    Command,
    SetupCommand,
    ListCommand,
    ConnectCommand,
    ConnectAllCommand,
)


class Display(Protocol):
    """Protocol for display output."""

    def print(self, message: str) -> None: ...
    def input(self, prompt: str) -> str: ...
    def error(self, message: str) -> None: ...


class TUIRenderer(Protocol):
    """Protocol for TUI rendering."""

    def display(self, state: VPNState, vpn_names: "str | List[str]") -> None: ...
    def setup(self) -> None: ...
    def cleanup(self) -> None: ...
    def show_cursor(self) -> None: ...
    def hide_cursor(self) -> None: ...
    def position_input(self, prompt: str, vpn_names: "str | List[str]") -> None: ...


class CommandHandler(ABC):
    """Base command handler."""

    @abstractmethod
    def handle(self, command: Command) -> bool:
        """Handle command, return True on success."""


class SetupHandler(CommandHandler):
    """Interactive setup wizard."""

    def __init__(
        self,
        xdg: XDGPaths,
        runner: CommandRunner,
        display: Display,
        store: Optional[CredentialStore] = None,
    ):
        self.xdg = xdg
        self.runner = runner
        self.display = display
        self.store = store
        self.config: Optional[AppConfig] = None
        self.modified = False
        self.is_new_config = False

    def handle(self, command: SetupCommand) -> bool:
        self.xdg.ensure_dirs()
        self._load_or_create_config()

        if self.is_new_config:
            self._first_time_setup()
        else:
            self._main_menu()

        return True

    def _load_or_create_config(self) -> None:
        """Load existing config or create empty one."""
        if self.xdg.config_file.exists():
            try:
                self.config = AppConfig.load(self.xdg.config_file)
                self.is_new_config = False
            except Exception as e:
                self.display.error(f"Error loading config: {e}")
                self.config = AppConfig.empty(self.xdg)
                self.is_new_config = True
        else:
            self.config = AppConfig.empty(self.xdg)
            self.is_new_config = True

    def _first_time_setup(self) -> None:
        """Guide user through first-time setup."""
        self.display.print("\nVPN Client Setup")
        self.display.print("=" * 40)
        self.display.print("\nNo existing configuration found.\n")

        # Step 1: Add VPNs
        self._add_vpn()
        while True:
            response = self.display.input("\nAdd another VPN? [Y/n]: ").strip().lower()
            if response == "n":
                break
            self._add_vpn()

        # Step 2: Username (after VPNs)
        self.display.print("")
        username = self.display.input(
            "Username (leave empty to prompt each time): "
        ).strip()
        self.config.username = username

        # Step 3: Credentials (if username provided)
        if username:
            response = (
                self.display.input("\nConfigure password store? [Y/n]: ")
                .strip()
                .lower()
            )
            if response != "n":
                self._configure_credentials()

        # Save
        self._save_config()
        self.display.print("\nSetup complete!")

    def _main_menu(self) -> None:
        """Display main menu and handle choices."""
        while True:
            self._show_status()
            self.display.print("\n[1] Add VPN")
            self.display.print("[2] Edit VPN")
            self.display.print("[3] Remove VPN")
            self.display.print("[4] Change username")
            self.display.print("[5] Configure credentials (GPG/password)")
            self.display.print("[6] Save and exit")
            self.display.print("[0] Exit without saving")

            choice = self.display.input("\nChoice: ").strip()

            if choice == "1":
                self._add_vpn()
            elif choice == "2":
                self._edit_vpn()
            elif choice == "3":
                self._remove_vpn()
            elif choice == "4":
                self._change_username()
            elif choice == "5":
                self._configure_credentials()
            elif choice == "6":
                self._save_config()
                self.display.print("\nConfiguration saved!")
                break
            elif choice == "0":
                if self.modified:
                    confirm = (
                        self.display.input("Discard changes? [y/N]: ").strip().lower()
                    )
                    if confirm != "y":
                        continue
                self.display.print("\nExiting without saving.")
                break

    def _show_status(self) -> None:
        """Show current configuration status."""
        self.display.print("\n" + "=" * 40)
        self.display.print("VPN Client Configuration")
        self.display.print("=" * 40)

        if self.config.vpns:
            vpn_names = ", ".join(v.name for v in self.config.vpns)
            self.display.print(
                f"  VPNs configured: {len(self.config.vpns)} ({vpn_names})"
            )
        else:
            self.display.print("  VPNs configured: none")

        if self.config.username:
            self.display.print(f"  Username: {self.config.username}")
        else:
            self.display.print("  Username: not set (will prompt)")

        if self.config.is_credentials_configured():
            self.display.print("  Credentials: configured")
        else:
            self.display.print("  Credentials: not set (will prompt)")

    def _add_vpn(self) -> None:
        """Interactive VPN addition wizard."""
        self.display.print("\nAdd VPN")
        self.display.print("-" * 20)

        name = self.display.input("VPN name: ").strip().upper()
        if not name:
            self.display.error("VPN name is required")
            return

        default_display = name
        display_name = (
            self.display.input(f"Display name [{default_display}]: ").strip()
            or default_display
        )

        config_path_str = self.display.input("Config file path: ").strip()
        if not config_path_str:
            self.display.error("Config file path is required")
            return

        config_path = Path(config_path_str).expanduser()
        if not config_path.exists():
            self.display.print(f"Warning: File not found: {config_path}")
            confirm = self.display.input("Continue anyway? [y/N]: ").strip().lower()
            if confirm != "y":
                return

        needs_up = self.display.input("Needs up script? [y/N]: ").strip().lower() == "y"

        vpn = VPNConfig(
            name=name,
            display_name=display_name,
            config_path=config_path,
            needs_up_script=needs_up,
        )
        self.config.add_vpn(vpn)
        self.modified = True
        self.display.print(f"\nVPN '{name}' added.")

    def _edit_vpn(self) -> None:
        """Select and edit existing VPN."""
        if not self.config.vpns:
            self.display.print("\nNo VPNs configured.")
            return

        self.display.print("\nSelect VPN to edit:")
        for i, vpn in enumerate(self.config.vpns, 1):
            self.display.print(f"  [{i}] {vpn.name} - {vpn.display_name}")
        self.display.print("  [0] Cancel")

        choice = self.display.input("\nChoice: ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(self.config.vpns):
                return
        except ValueError:
            return

        old_vpn = self.config.vpns[idx]
        self.display.print(f"\nEditing {old_vpn.name}")
        self.display.print("-" * 20)

        display_name = (
            self.display.input(f"Display name [{old_vpn.display_name}]: ").strip()
            or old_vpn.display_name
        )

        config_path_str = self.display.input(
            f"Config file path [{old_vpn.config_path}]: "
        ).strip() or str(old_vpn.config_path)
        config_path = Path(config_path_str).expanduser()

        needs_default = "Y" if old_vpn.needs_up_script else "N"
        needs_up_str = (
            self.display.input(f"Needs up script? [y/n] ({needs_default}): ")
            .strip()
            .lower()
        )
        if needs_up_str == "y":
            needs_up = True
        elif needs_up_str == "n":
            needs_up = False
        else:
            needs_up = old_vpn.needs_up_script

        new_vpn = VPNConfig(
            name=old_vpn.name,
            display_name=display_name,
            config_path=config_path,
            needs_up_script=needs_up,
            up_script=old_vpn.up_script,
        )
        self.config.vpns[idx] = new_vpn
        self.modified = True
        self.display.print(f"\nVPN '{old_vpn.name}' updated.")

    def _remove_vpn(self) -> None:
        """Select and remove VPN."""
        if not self.config.vpns:
            self.display.print("\nNo VPNs configured.")
            return

        self.display.print("\nSelect VPN to remove:")
        for i, vpn in enumerate(self.config.vpns, 1):
            self.display.print(f"  [{i}] {vpn.name} - {vpn.display_name}")
        self.display.print("  [0] Cancel")

        choice = self.display.input("\nChoice: ").strip()
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(self.config.vpns):
                return
        except ValueError:
            return

        vpn = self.config.vpns[idx]
        confirm = self.display.input(f"Remove '{vpn.name}'? [y/N]: ").strip().lower()
        if confirm == "y":
            self.config.remove_vpn(vpn.name)
            self.modified = True
            self.display.print(f"\nVPN '{vpn.name}' removed.")

    def _change_username(self) -> None:
        """Prompt for new username."""
        current = self.config.username or "(not set)"
        self.display.print(f"\nCurrent username: {current}")
        username = self.display.input(
            "New username (leave empty to prompt each time): "
        ).strip()
        self.config.username = username
        self.modified = True
        if username:
            self.display.print(f"\nUsername set to: {username}")
        else:
            self.display.print("\nUsername cleared (will prompt at connection).")

    def _configure_credentials(self) -> None:
        """GPG and password setup."""
        if not self._check_gpg():
            return

        gpg_id = self.display.input("\nGPG key ID: ").strip()
        if not gpg_id:
            self.display.error("GPG key ID is required")
            return

        if not self.store:
            # Import here to avoid circular dependency
            from infrastructure.password_store import PassPasswordStore

            self.store = PassPasswordStore(self.config.credentials_dir)

        self.display.print("\nInitializing password store...")
        if not self.store.initialize(gpg_id):
            self.display.error("Error: Failed to init password store")
            return

        if self.config.username:
            self.display.print("\nEnter password:")
            if not self.store.store_password(self.config.username):
                self.display.error("Error: Failed to store password")
                return
            self.display.print("\nCredentials configured!")
        else:
            self.display.print(
                "\nPassword store initialized. Set username to store password."
            )

    def _check_gpg(self) -> bool:
        """Check if GPG keys are available."""
        result = self.runner.run(["gpg", "--list-secret-keys"])
        if "sec" not in result.stdout:
            self.display.error("Error: No GPG keys. Run: gpg --gen-key")
            return False
        self.display.print("\nGPG keys:")
        result = self.runner.run(
            ["gpg", "--list-secret-keys", "--keyid-format", "SHORT"]
        )
        for line in result.stdout.split("\n")[:10]:
            if line.strip():
                self.display.print(line)
        return True

    def _save_config(self) -> None:
        """Save config to XDG config file."""
        self.config.save(self.xdg.config_file)
        self.modified = False


class ListHandler(CommandHandler):
    """Handle list command."""

    def __init__(self, service: VPNService, display: Display):
        self.service = service
        self.display = display

    def handle(self, command: ListCommand) -> bool:
        self.display.print("Available VPNs:")
        for vpn in self.service.list_vpns():
            self.display.print(f"  {vpn}")
        return True


class ConnectHandler(CommandHandler):
    """Handle single VPN connection with TUI."""

    # Map management states to domain status
    STATE_MAP = {
        ManagementState.CONNECTING: Status.CONNECTING,
        ManagementState.WAIT: Status.CONNECTING,
        ManagementState.AUTH: Status.CONNECTING,
        ManagementState.GET_CONFIG: Status.CONNECTING,
        ManagementState.ASSIGN_IP: Status.CONNECTING,
        ManagementState.ADD_ROUTES: Status.CONNECTING,
        ManagementState.CONNECTED: Status.CONNECTED,
        ManagementState.RECONNECTING: Status.CONNECTING,
        ManagementState.EXITING: Status.DISCONNECTED,
        ManagementState.RESOLVE: Status.CONNECTING,
        ManagementState.TCP_CONNECT: Status.CONNECTING,
    }

    def __init__(
        self,
        service: VPNService,
        store: CredentialStore,
        username: str,
        tui: TUIRenderer,
        display: Display,
        config_dir: Path,
    ):
        self.service = service
        self.store = store
        self.username = username
        self.tui = tui
        self.display = display
        self.config_dir = config_dir
        self.state = VPNState()
        self.log_path: Optional[Path] = None
        self.management_port: Optional[int] = None
        self.management_client: Optional[ManagementClient] = None
        self.last_bytecount_time: float = 0
        self.running = True
        self.success = False

    def handle(self, command: ConnectCommand) -> bool:
        if not self.service.validate_vpn(command.vpn_type):
            self.display.error(f"Error: Unknown VPN: {command.vpn_type}")
            return False

        self.vpn_type = command.vpn_type
        self._setup_signals()
        self._start_sudo_refresh()
        self.tui.setup()

        try:
            self.log_path = Path(f"/tmp/{self.vpn_type.log_prefix}-{os.getpid()}.log")
            self.state.set_log(self.vpn_type, str(self.log_path))

            if not self._connect_vpn():
                return False

            self.success = True
            self._monitor_loop()
            return True
        finally:
            self._cleanup()

    def _connect_vpn(self) -> bool:
        # Check/setup management interface
        self._setup_management()

        while self.running:
            self.state.set_status(self.vpn_type, Status.WAITING)
            code = self._prompt_2fa()
            if not code:
                return False

            credentials = self._get_credentials(code)
            if not credentials:
                return False

            self.service.connect(
                self.vpn_type, credentials, self.log_path, self.management_port
            )
            result = self._wait_for_connection()

            if result == ConnectionResult.CONNECTED:
                self.state.set_status(self.vpn_type, Status.CONNECTED)
                return True

            self._reset_vpn()
        return False

    def _setup_management(self) -> None:
        """Check for management directive and prompt user if missing."""
        config_path = self.config_dir / self.vpn_type.config_filename
        parser = OpenVPNConfigParser(config_path)

        if parser.has_management_directive():
            config = parser.get_management_config()
            self.management_port = config.port
            return

        if self._prompt_management_setup():
            port = PortAllocator.allocate()
            parser.append_management_directive("127.0.0.1", port)
            self.management_port = port

    def _prompt_management_setup(self) -> bool:
        """Prompt user to enable management interface."""
        self.state.prompt = "Management interface not found. Enable it? [Y/n]: "
        self.tui.show_cursor()
        self.tui.display(self.state, self.vpn_type.name)
        self.tui.position_input(self.state.prompt, self.vpn_type.name)
        old_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            response = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            self.running = False
            print(flush=True)
            response = "n"
        finally:
            signal.signal(signal.SIGINT, old_handler)
        self.tui.hide_cursor()
        self.state.prompt = ""
        return response != "n"

    def _prompt_2fa(self) -> str:
        self.state.prompt = "2FA code: "
        self.tui.show_cursor()
        self.tui.display(self.state, self.vpn_type.name)
        self.tui.position_input(self.state.prompt, self.vpn_type.name)
        old_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            code = input().strip()
        except (KeyboardInterrupt, EOFError):
            self.running = False
            print(flush=True)
            code = ""
        finally:
            signal.signal(signal.SIGINT, old_handler)
        self.tui.hide_cursor()
        self.state.prompt = ""
        return code

    def _get_credentials(self, otp: str) -> Optional[Credentials]:
        password = self.store.get_password(self.username)
        if not password:
            return None
        return Credentials(self.username, password, otp)

    def _wait_for_connection(self) -> ConnectionResult:
        if self.management_port:
            return self._wait_via_management()
        return self._wait_via_log()

    def _wait_via_log(self) -> ConnectionResult:
        """Wait for connection using log file polling."""

        def tick():
            self.state.set_status(self.vpn_type, Status.CONNECTING)
            self.state.advance_spinner()
            self.tui.display(self.state, self.vpn_type.name)

        return self.service.wait_for_connection(self.vpn_type, self.log_path, tick)

    def _wait_via_management(self) -> ConnectionResult:
        """Wait for connection using management interface."""
        client = ManagementClient(port=self.management_port)

        if not client.connect():
            return self._wait_via_log()

        self.management_client = client
        self.last_bytecount_time = time.time()
        client.send_command("state on")
        client.send_command("bytecount 5")

        timeout = 60
        for _ in range(int(timeout / 0.1)):
            self.state.set_status(self.vpn_type, Status.CONNECTING)
            self.state.advance_spinner()
            self._update_bandwidth(client)
            self.tui.display(self.state, self.vpn_type.name)

            events = client.read_events()
            for event in events:
                status = self.STATE_MAP.get(event.state)
                if status:
                    self.state.set_status(self.vpn_type, status)
                if event.state == ManagementState.CONNECTED:
                    return ConnectionResult.CONNECTED
                if event.state == ManagementState.EXITING:
                    return ConnectionResult.PROCESS_DIED

            if not self.service.is_connected(self.vpn_type):
                time.sleep(0.5)
                return ConnectionResult.PROCESS_DIED

            time.sleep(0.1)

        return ConnectionResult.TIMEOUT

    def _update_bandwidth(self, client: ManagementClient) -> None:
        """Update bandwidth stats from management client."""
        bytecount = client.get_bytecount()
        if bytecount:
            stats = self.state.get_bandwidth(self.vpn_type)
            if (
                bytecount.bytes_in != stats.total_in
                or bytecount.bytes_out != stats.total_out
            ):
                now = time.time()
                interval = now - self.last_bytecount_time
                self.last_bytecount_time = now
                stats.update(bytecount.bytes_in, bytecount.bytes_out, interval)

    def _reset_vpn(self) -> None:
        self.state.set_status(self.vpn_type, Status.DISCONNECTED)
        self.service.disconnect(self.vpn_type)

    def _monitor_loop(self) -> None:
        check_interval = 20
        iteration = 0

        while self.running:
            if self.management_client:
                self.management_client.read_events()
                self._update_bandwidth(self.management_client)

            self.tui.display(self.state, self.vpn_type.name)
            time.sleep(0.1)
            iteration += 1

            if iteration < check_interval:
                continue
            iteration = 0

            if not self.service.is_connected(self.vpn_type) or self.service.has_errors(
                self.log_path
            ):
                self._reset_vpn()
                if not self._connect_vpn():
                    self.success = False
                    break

    def _setup_signals(self) -> None:
        def handler(*_):
            self.running = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _start_sudo_refresh(self) -> None:
        def refresh():
            runner = CommandRunner()
            while self.running:
                runner.run_sudo(["-v"])
                time.sleep(50)

        threading.Thread(target=refresh, daemon=True).start()

    def _cleanup(self) -> None:
        self.tui.cleanup()

        if self.management_client:
            self.management_client.disconnect()
            self.management_client = None

        if self.management_port:
            PortAllocator.release(self.management_port)
            self.management_port = None

        self.service.disconnect(self.vpn_type)
        if self.success and self.log_path:
            self.service.cleanup(self.log_path)


class ConnectAllHandler(CommandHandler):
    """Handle multi-VPN connection with TUI for N VPNs."""

    # Map management states to domain status
    STATE_MAP = {
        ManagementState.CONNECTING: Status.CONNECTING,
        ManagementState.WAIT: Status.CONNECTING,
        ManagementState.AUTH: Status.CONNECTING,
        ManagementState.GET_CONFIG: Status.CONNECTING,
        ManagementState.ASSIGN_IP: Status.CONNECTING,
        ManagementState.ADD_ROUTES: Status.CONNECTING,
        ManagementState.CONNECTED: Status.CONNECTED,
        ManagementState.RECONNECTING: Status.CONNECTING,
        ManagementState.EXITING: Status.DISCONNECTED,
        ManagementState.RESOLVE: Status.CONNECTING,
        ManagementState.TCP_CONNECT: Status.CONNECTING,
    }

    def __init__(
        self,
        service: VPNService,
        store: CredentialStore,
        username: str,
        tui: TUIRenderer,
        display: Display,
        config_paths: Dict[str, Path],
        vpn_types: List[VPNType],
    ):
        self.service = service
        self.store = store
        self.username = username
        self.tui = tui
        self.display = display
        self.config_paths = config_paths
        self.vpn_types = vpn_types
        self.vpn_names = [v.name for v in vpn_types]
        self.state = VPNState()
        self.state.initialize(self.vpn_names)
        self.logs: Dict[str, Optional[Path]] = {name: None for name in self.vpn_names}
        self.management_ports: Dict[str, int] = {}
        self.management_clients: Dict[str, ManagementClient] = {}
        self.last_bytecount_time: Dict[str, float] = {}
        self.running = True
        self.success = False

    def handle(self, command: ConnectAllCommand) -> bool:
        self._setup_signals()
        self._start_sudo_refresh()
        self.tui.setup()

        try:
            # Set log paths for all VPNs
            for vpn_type in self.vpn_types:
                self.state.set_log(vpn_type, str(self._log_path(vpn_type)))

            # Connect to each VPN in order
            for vpn_type in self.vpn_types:
                if not self._connect_vpn(vpn_type):
                    return False

            self.success = True
            self._monitor_loop()
            return True
        finally:
            self._cleanup()

    def _log_path(self, vpn_type: VPNType) -> Path:
        key = vpn_type.name
        if not self.logs[key]:
            self.logs[key] = Path(f"/tmp/{vpn_type.log_prefix}-{os.getpid()}.log")
        return self.logs[key]

    def _connect_vpn(self, vpn_type: VPNType) -> bool:
        log = self._log_path(vpn_type)

        # Check/setup management interface on first attempt
        if vpn_type.name not in self.management_ports:
            self._setup_management(vpn_type)

        management_port = self.management_ports.get(vpn_type.name)

        while self.running:
            self.state.set_status(vpn_type, Status.WAITING)
            code = self._prompt_2fa(vpn_type)
            if not code:
                return False

            credentials = self._get_credentials(code)
            if not credentials:
                return False

            self.service.connect(vpn_type, credentials, log, management_port)
            result = self._wait_for_connection(vpn_type, log)

            if result == ConnectionResult.CONNECTED:
                self.state.set_status(vpn_type, Status.CONNECTED)
                return True

            self._reset_vpn(vpn_type)
        return False

    def _setup_management(self, vpn_type: VPNType) -> None:
        """Check for management directive and prompt user if missing."""
        config_path = self.config_paths.get(vpn_type.name)
        if not config_path:
            return
        parser = OpenVPNConfigParser(config_path)

        if parser.has_management_directive():
            config = parser.get_management_config()
            self.management_ports[vpn_type.name] = config.port
            return

        if self._prompt_management_setup():
            port = PortAllocator.allocate()
            parser.append_management_directive("127.0.0.1", port)
            self.management_ports[vpn_type.name] = port

    def _prompt_management_setup(self) -> bool:
        """Prompt user to enable management interface."""
        self.state.prompt = "Management interface not found. Enable it? [Y/n]: "
        self.tui.show_cursor()
        self.tui.display(self.state, self.vpn_names)
        self.tui.position_input(self.state.prompt, self.vpn_names)
        old_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            response = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            self.running = False
            print(flush=True)
            response = "n"
        finally:
            signal.signal(signal.SIGINT, old_handler)
        self.tui.hide_cursor()
        self.state.prompt = ""
        return response != "n"

    def _prompt_2fa(self, vpn_type: VPNType) -> str:
        self.state.prompt = f"{vpn_type.name} 2FA code: "
        self.tui.show_cursor()
        self.tui.display(self.state, self.vpn_names)
        self.tui.position_input(self.state.prompt, self.vpn_names)
        old_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            code = input().strip()
        except (KeyboardInterrupt, EOFError):
            self.running = False
            print(flush=True)
            code = ""
        finally:
            signal.signal(signal.SIGINT, old_handler)
        self.tui.hide_cursor()
        self.state.prompt = ""
        return code

    def _get_credentials(self, otp: str) -> Optional[Credentials]:
        password = self.store.get_password(self.username)
        if not password:
            return None
        return Credentials(self.username, password, otp)

    def _wait_for_connection(self, vpn_type: VPNType, log: Path) -> ConnectionResult:
        port = self.management_ports.get(vpn_type.name)
        if port:
            return self._wait_via_management(vpn_type, port, log)
        return self._wait_via_log(vpn_type, log)

    def _wait_via_log(self, vpn_type: VPNType, log: Path) -> ConnectionResult:
        """Wait for connection using log file polling."""

        def tick():
            self.state.set_status(vpn_type, Status.CONNECTING)
            self.state.advance_spinner()
            self.tui.display(self.state, self.vpn_names)

        return self.service.wait_for_connection(vpn_type, log, tick)

    def _wait_via_management(
        self, vpn_type: VPNType, port: int, log: Path
    ) -> ConnectionResult:
        """Wait for connection using management interface."""
        client = ManagementClient(port=port)

        # Try to connect to management interface
        if not client.connect():
            # Fall back to log-based polling
            return self._wait_via_log(vpn_type, log)

        self.management_clients[vpn_type.name] = client
        self.last_bytecount_time[vpn_type.name] = time.time()
        client.send_command("state on")
        client.send_command("bytecount 5")

        timeout = 60
        for _ in range(int(timeout / 0.1)):
            self.state.set_status(vpn_type, Status.CONNECTING)
            self.state.advance_spinner()
            self._update_bandwidth(vpn_type, client)
            self.tui.display(self.state, self.vpn_names)

            events = client.read_events()
            for event in events:
                status = self.STATE_MAP.get(event.state)
                if status:
                    self.state.set_status(vpn_type, status)
                if event.state == ManagementState.CONNECTED:
                    return ConnectionResult.CONNECTED
                if event.state == ManagementState.EXITING:
                    return ConnectionResult.PROCESS_DIED

            if not self.service.is_connected(vpn_type):
                time.sleep(0.5)
                return ConnectionResult.PROCESS_DIED

            time.sleep(0.1)

        return ConnectionResult.TIMEOUT

    def _update_bandwidth(self, vpn_type: VPNType, client: ManagementClient) -> None:
        """Update bandwidth stats from management client."""
        bytecount = client.get_bytecount()
        if bytecount:
            stats = self.state.get_bandwidth(vpn_type)
            # Only update timestamp when bytes actually change
            if (
                bytecount.bytes_in != stats.total_in
                or bytecount.bytes_out != stats.total_out
            ):
                now = time.time()
                last = self.last_bytecount_time.get(vpn_type.name, now)
                interval = now - last
                self.last_bytecount_time[vpn_type.name] = now
                stats.update(bytecount.bytes_in, bytecount.bytes_out, interval)

    def _reset_vpn(self, vpn_type: VPNType) -> None:
        self.state.set_status(vpn_type, Status.DISCONNECTED)
        self.service.disconnect(vpn_type)

    def _monitor_loop(self) -> None:
        check_interval = 20  # Check connection health every 20 iterations (2 sec)
        iteration = 0

        while self.running:
            # Update bandwidth from management clients
            for vpn_name, client in self.management_clients.items():
                vpn = VPNType(vpn_name)
                client.read_events()  # Process any pending events
                self._update_bandwidth(vpn, client)

            self.tui.display(self.state, self.vpn_names)
            time.sleep(0.1)
            iteration += 1

            # Only check connection health periodically
            if iteration < check_interval:
                continue
            iteration = 0

            # Check each VPN for errors - reconnect from failed one onwards
            for i, vpn_type in enumerate(self.vpn_types):
                log = self._log_path(vpn_type)
                is_bad = not self.service.is_connected(
                    vpn_type
                ) or self.service.has_errors(log)

                if is_bad:
                    # Reset this VPN and all following ones
                    for v in self.vpn_types[i:]:
                        self._reset_vpn(v)
                    # Reconnect from this VPN onwards
                    for v in self.vpn_types[i:]:
                        if not self._connect_vpn(v):
                            self.success = False
                            return
                    break

    def _setup_signals(self) -> None:
        def handler(*_):
            self.running = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _start_sudo_refresh(self) -> None:
        def refresh():
            runner = CommandRunner()
            while self.running:
                runner.run_sudo(["-v"])
                time.sleep(50)

        threading.Thread(target=refresh, daemon=True).start()

    def _cleanup(self) -> None:
        self.tui.cleanup()

        # Disconnect management clients
        for client in self.management_clients.values():
            client.disconnect()
        self.management_clients.clear()

        # Release allocated ports
        for port in self.management_ports.values():
            PortAllocator.release(port)
        self.management_ports.clear()

        # Disconnect and cleanup all VPNs
        for vpn_type in self.vpn_types:
            self.service.disconnect(vpn_type)
            if self.success:
                log = self.logs.get(vpn_type.name)
                if log:
                    self.service.cleanup(log)
