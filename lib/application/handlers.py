"""Command handlers - execute use cases."""

import os
import signal
import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Protocol

from domain import VPNType, VPNState, Status, Credentials, ConnectionResult
from domain.services import VPNService, CredentialStore
from infrastructure.process import CommandRunner
from application.commands import (
    Command,
    SetupCommand,
    ListCommand,
    ConnectCommand,
    ConnectBothCommand,
)


class Display(Protocol):
    """Protocol for display output."""

    def print(self, message: str) -> None: ...
    def input(self, prompt: str) -> str: ...
    def error(self, message: str) -> None: ...


class TUIRenderer(Protocol):
    """Protocol for TUI rendering."""

    def display(self, state: VPNState) -> None: ...
    def setup(self) -> None: ...
    def cleanup(self) -> None: ...
    def show_cursor(self) -> None: ...
    def hide_cursor(self) -> None: ...
    def position_input(self, prompt: str) -> None: ...


class CommandHandler(ABC):
    """Base command handler."""

    @abstractmethod
    def handle(self, command: Command) -> bool:
        """Handle command, return True on success."""


class SetupHandler(CommandHandler):
    """Handle setup command."""

    def __init__(
        self,
        store: CredentialStore,
        runner: CommandRunner,
        base_path: Path,
        display: Display,
    ):
        self.store = store
        self.runner = runner
        self.base_path = base_path
        self.display = display

    def handle(self, command: SetupCommand) -> bool:
        self.display.print("VPN Setup\n")

        if not self._check_gpg():
            return False

        gpg_id = self.display.input("\nGPG key ID: ").strip()
        username = self.display.input("ICIJ username: ").strip()

        if not gpg_id or not username:
            self.display.error("Error: Both GPG ID and username required")
            return False

        self._save_username(username)
        return self._init_store(gpg_id, username)

    def _check_gpg(self) -> bool:
        result = self.runner.run(["gpg", "--list-secret-keys"])
        if "sec" not in result.stdout:
            self.display.error("Error: No GPG keys. Run: gpg --gen-key")
            return False
        self.display.print("GPG keys:")
        result = self.runner.run(
            ["gpg", "--list-secret-keys", "--keyid-format", "SHORT"]
        )
        for line in result.stdout.split("\n")[:10]:
            if line.strip():
                self.display.print(line)
        return True

    def _save_username(self, username: str) -> None:
        (self.base_path / ".username").write_text(username)

    def _init_store(self, gpg_id: str, username: str) -> bool:
        self.display.print("\nInitializing password store...")
        if not self.store.initialize(gpg_id):
            self.display.error("Error: Failed to init password store")
            return False
        self.display.print("\nEnter ICIJ password:")
        if not self.store.store_password(username):
            self.display.error("Error: Failed to store password")
            return False
        self.display.print("\nSetup complete!")
        return True


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
    """Handle single VPN connection."""

    def __init__(
        self,
        service: VPNService,
        store: CredentialStore,
        username: str,
        base_path: Path,
        display: Display,
    ):
        self.service = service
        self.store = store
        self.username = username
        self.base_path = base_path
        self.display = display

    def handle(self, command: ConnectCommand) -> bool:
        if not self.service.validate_vpn(command.vpn_type):
            self.display.error(f"Error: Unknown VPN: {command.vpn_type}")
            return False

        code = self.display.input("2FA code: ").strip()
        if not code:
            self.display.error("Error: 2FA code required")
            return False

        credentials = self._get_credentials(code)
        if not credentials:
            self.display.error("Error: Could not get credentials")
            return False

        return self._run_vpn(command.vpn_type, credentials)

    def _get_credentials(self, otp: str) -> Optional[Credentials]:
        password = self.store.get_password(self.username)
        if not password:
            return None
        return Credentials(self.username, password, otp)

    def _run_vpn(self, vpn_type: VPNType, credentials: Credentials) -> bool:
        import subprocess

        auth_file = Path(f"/tmp/vpn-auth-{os.getpid()}")
        auth_file.write_text(credentials.auth_string)

        cmd = [
            "sudo",
            "openvpn",
            "--config",
            str(self.base_path / "certificates" / vpn_type.config_filename),
        ]
        if self.service.needs_up_script(vpn_type):
            cmd.extend(
                [
                    "--script-security",
                    "2",
                    "--up",
                    str(self.base_path / "scripts" / "up.sh"),
                ]
            )
        cmd.extend(["--auth-user-pass", str(auth_file)])

        try:
            subprocess.run(cmd)
            return True
        finally:
            auth_file.unlink(missing_ok=True)


class ConnectBothHandler(CommandHandler):
    """Handle dual VPN connection with TUI."""

    UP_SCRIPT_VPNS = ["EXT"]

    def __init__(
        self,
        service: VPNService,
        store: CredentialStore,
        username: str,
        tui: TUIRenderer,
        display: Display,
    ):
        self.service = service
        self.store = store
        self.username = username
        self.tui = tui
        self.display = display
        self.state = VPNState()
        self.logs = {"EXT": None, "INT": None}
        self.running = True
        self.success = False

    def handle(self, command: ConnectBothCommand) -> bool:
        self._setup_signals()
        self._start_sudo_refresh()
        self.tui.setup()

        try:
            ext = VPNType("EXT")
            int_ = VPNType("INT")

            self.state.ext_log = str(self._log_path(ext))
            self.state.int_log = str(self._log_path(int_))

            if not self._connect_vpn(ext) or not self._connect_vpn(int_):
                return False

            self.success = True
            self._monitor_loop(ext, int_)
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
        while self.running:
            self.state.set_status(vpn_type, Status.WAITING)
            code = self._prompt_2fa()
            if not code:
                return False

            credentials = self._get_credentials(code)
            if not credentials:
                return False

            self.service.connect(vpn_type, credentials, log)
            result = self._wait_for_connection(vpn_type, log)

            if result == ConnectionResult.CONNECTED:
                self.state.set_status(vpn_type, Status.CONNECTED)
                return True

            self._reset_vpn(vpn_type)
        return False

    def _prompt_2fa(self) -> str:
        self.state.prompt = "2FA code: "
        self.tui.show_cursor()
        self.tui.display(self.state)
        self.tui.position_input(self.state.prompt)
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
        def tick():
            self.state.set_status(vpn_type, Status.CONNECTING)
            self.state.advance_spinner()
            self.tui.display(self.state)

        return self.service.wait_for_connection(vpn_type, log, tick)

    def _reset_vpn(self, vpn_type: VPNType) -> None:
        self.state.set_status(vpn_type, Status.DISCONNECTED)
        self.service.disconnect(vpn_type)

    def _monitor_loop(self, ext: VPNType, int_: VPNType) -> None:
        while self.running:
            self.tui.display(self.state)
            time.sleep(2)

            ext_log, int_log = self._log_path(ext), self._log_path(int_)
            ext_bad = not self.service.is_connected(ext) or self.service.has_errors(
                ext_log
            )
            int_bad = not self.service.is_connected(int_) or self.service.has_errors(
                int_log
            )

            if ext_bad:
                self._reset_vpn(ext)
                self._reset_vpn(int_)
                if not self._connect_vpn(ext) or not self._connect_vpn(int_):
                    self.success = False
                    break
            elif int_bad:
                self._reset_vpn(int_)
                if not self._connect_vpn(int_):
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
        for vpn_name in ["EXT", "INT"]:
            vpn = VPNType(vpn_name)
            self.service.disconnect(vpn)
            if self.success:
                log = self.logs.get(vpn_name)
                if log:
                    self.service.cleanup(log)
