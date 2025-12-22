"""OpenVPN process management."""

from pathlib import Path
from typing import Optional, List

from domain.services import ProcessManager
from domain.value_objects import VPNType, Credentials, ConnectionResult
from infrastructure.process import CommandRunner


ERROR_PATTERNS = [
    "Network is unreachable",
    "Connection refused",
    "Connection timed out",
]


class OpenVPNProcessManager(ProcessManager):
    """Manages OpenVPN processes."""

    def __init__(
        self, runner: CommandRunner, config_dir: Path, up_script: Optional[Path] = None
    ):
        self.runner = runner
        self.config_dir = config_dir
        self.up_script = up_script

    def _config_path(self, vpn_type: VPNType) -> Path:
        return self.config_dir / vpn_type.config_filename

    def _build_command(
        self,
        vpn_type: VPNType,
        auth_file: Path,
        use_up_script: bool,
        management_port: Optional[int] = None,
    ) -> List[str]:
        """Build OpenVPN command."""
        cmd = ["sudo", "openvpn", "--config", str(self._config_path(vpn_type))]
        if use_up_script and self.up_script:
            cmd.extend(["--script-security", "2", "--up", str(self.up_script)])
        if management_port:
            cmd.extend(["--management", "127.0.0.1", str(management_port)])
        cmd.extend(["--auth-user-pass", str(auth_file)])
        return cmd

    def start(
        self,
        vpn_type: VPNType,
        credentials: Credentials,
        log_path: Path,
        use_up_script: bool,
        management_port: Optional[int] = None,
    ) -> None:
        """Start VPN connection in background."""
        auth_file = log_path.with_suffix(".auth")
        auth_file.write_text(credentials.auth_string)
        cmd = self._build_command(vpn_type, auth_file, use_up_script, management_port)
        self.runner.start_background(cmd, str(log_path))

    def stop(self, vpn_type: VPNType) -> None:
        """Stop VPN process."""
        config = self._config_path(vpn_type)
        self.runner.run_sudo(["pkill", "-f", f"openvpn.*{config}"])

    def is_running(self, vpn_type: VPNType) -> bool:
        """Check if VPN process is running."""
        config = self._config_path(vpn_type)
        return self.runner.run_sudo(["pgrep", "-f", f"openvpn.*{config}"]).success

    def check_status(self, log_path: Path) -> Optional[ConnectionResult]:
        """Check connection status from log file."""
        content = self._read_log(log_path)
        if "Initialization Sequence Completed" in content:
            return ConnectionResult.CONNECTED
        if "AUTH_FAILED" in content:
            return ConnectionResult.AUTH_FAILED
        return None

    def has_errors(self, log_path: Path) -> bool:
        """Check if log contains error patterns."""
        if not log_path.exists():
            return False
        result = self.runner.run_sudo(["tail", "-20", str(log_path)])
        return any(p in result.stdout for p in ERROR_PATTERNS)

    def cleanup(self, log_path: Path) -> None:
        """Clean up log and auth files."""
        self.runner.run_sudo(["rm", "-f", str(log_path)])
        self.runner.run_sudo(["rm", "-f", str(log_path.with_suffix(".auth"))])

    def _read_log(self, log_path: Path) -> str:
        """Read log file content."""
        result = self.runner.run(["cat", str(log_path)])
        if not result.success:
            result = self.runner.run_sudo(["cat", str(log_path)])
        return result.stdout
