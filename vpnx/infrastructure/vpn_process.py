"""OpenVPN process management."""

from pathlib import Path
from typing import Dict, List, Optional

from vpnx.domain.services import ProcessManager
from vpnx.domain.value_objects import ConnectionResult, Credentials, TunMTU, VPNType
from vpnx.infrastructure.process import CommandRunner

ERROR_PATTERNS = [
    "Network is unreachable",
    "Connection refused",
    "Connection timed out",
]


class OpenVPNProcessManager(ProcessManager):
    """Manages OpenVPN processes.

    Supports two modes:
    1. Config-based: Explicit path mapping from VPN names to config files
    2. Directory-based (legacy): Use config_dir with VPNType.config_filename
    """

    def __init__(
        self,
        runner: CommandRunner,
        config_dir: Optional[Path] = None,
        up_script: Optional[Path] = None,
        down_script: Optional[Path] = None,
        config_paths: Optional[Dict[str, Path]] = None,
    ):
        self.runner = runner
        self.config_dir = config_dir
        self.up_script = up_script
        self.down_script = down_script
        self.config_paths = config_paths or {}

    def _config_path(self, vpn_type: VPNType) -> Path:
        # New mode: use explicit config paths
        name_upper = vpn_type.name.upper()
        if name_upper in self.config_paths:
            return self.config_paths[name_upper]

        # Legacy mode: construct from directory
        if self.config_dir:
            return self.config_dir / vpn_type.config_filename

        raise ValueError(f"No config path for VPN: {vpn_type.name}")

    def _build_command(
        self,
        vpn_type: VPNType,
        auth_file: Path,
        use_up_script: bool,
        use_down_script: bool = False,
        management_port: Optional[int] = None,
        tun_mtu: Optional[TunMTU] = None,
    ) -> List[str]:
        """Build OpenVPN command."""
        cmd = ["sudo", "openvpn", "--config", str(self._config_path(vpn_type))]
        if tun_mtu is not None:
            cmd.extend(["--tun-mtu", str(tun_mtu)])
        needs_script_security = (use_up_script and self.up_script) or (
            use_down_script and self.down_script
        )
        if needs_script_security:
            cmd.extend(["--script-security", "2"])
        if use_up_script and self.up_script:
            cmd.extend(["--up", str(self.up_script)])
        if use_down_script and self.down_script:
            cmd.extend(["--down", str(self.down_script)])
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
        use_down_script: bool = False,
        management_port: Optional[int] = None,
        tun_mtu: Optional[TunMTU] = None,
    ) -> None:
        """Start VPN connection in background."""
        auth_file = log_path.with_suffix(".auth")
        auth_file.write_text(credentials.auth_string)
        cmd = self._build_command(
            vpn_type,
            auth_file,
            use_up_script,
            use_down_script,
            management_port,
            tun_mtu,
        )
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
