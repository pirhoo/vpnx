"""Domain services - business logic that doesn't belong to entities."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional

from .value_objects import ConnectionResult, Credentials, TunMTU, VPNType


class VPNRepository(ABC):
    """Abstract repository for VPN operations."""

    @abstractmethod
    def list_available(self) -> List[VPNType]:
        """List available VPN configurations."""

    @abstractmethod
    def exists(self, vpn_type: VPNType) -> bool:
        """Check if VPN configuration exists."""

    @abstractmethod
    def config_path(self, vpn_type: VPNType) -> Path:
        """Get path to VPN config file."""


class ProcessManager(ABC):
    """Abstract interface for VPN process management."""

    @abstractmethod
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
        """Start VPN connection."""

    @abstractmethod
    def stop(self, vpn_type: VPNType) -> None:
        """Stop VPN connection."""

    @abstractmethod
    def is_running(self, vpn_type: VPNType) -> bool:
        """Check if VPN process is running."""

    @abstractmethod
    def check_status(self, log_path: Path) -> Optional[ConnectionResult]:
        """Check connection status from log."""

    @abstractmethod
    def has_errors(self, log_path: Path) -> bool:
        """Check if log contains errors."""

    @abstractmethod
    def cleanup(self, log_path: Path) -> None:
        """Clean up log and auth files."""


class CredentialStore(ABC):
    """Abstract interface for credential storage."""

    @abstractmethod
    def get_password(self, username: str) -> Optional[str]:
        """Get password for username."""

    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if store is initialized."""

    @abstractmethod
    def initialize(self, gpg_id: str) -> bool:
        """Initialize the store."""

    @abstractmethod
    def store_password(self, username: str) -> bool:
        """Store password for username (interactive)."""


class VPNService:
    """Domain service for VPN operations."""

    TIMEOUT = 60

    def __init__(
        self,
        repository: VPNRepository,
        process_manager: ProcessManager,
        up_script_vpns: Optional[List[str]] = None,
        down_script_vpns: Optional[List[str]] = None,
    ):
        self.repository = repository
        self.process_manager = process_manager
        self.up_script_vpns = up_script_vpns if up_script_vpns is not None else []
        self.down_script_vpns = down_script_vpns if down_script_vpns is not None else []

    def list_vpns(self) -> List[VPNType]:
        return self.repository.list_available()

    def validate_vpn(self, vpn_type: VPNType) -> bool:
        return self.repository.exists(vpn_type)

    def needs_up_script(self, vpn_type: VPNType) -> bool:
        return vpn_type.name in self.up_script_vpns

    def needs_down_script(self, vpn_type: VPNType) -> bool:
        return vpn_type.name in self.down_script_vpns

    def connect(
        self,
        vpn_type: VPNType,
        credentials: Credentials,
        log_path: Path,
        management_port: Optional[int] = None,
        tun_mtu: Optional[TunMTU] = None,
    ) -> None:
        """Start VPN connection."""
        self.process_manager.start(
            vpn_type,
            credentials,
            log_path,
            self.needs_up_script(vpn_type),
            self.needs_down_script(vpn_type),
            management_port,
            tun_mtu,
        )

    def disconnect(self, vpn_type: VPNType) -> None:
        """Stop VPN connection."""
        self.process_manager.stop(vpn_type)

    def is_connected(self, vpn_type: VPNType) -> bool:
        return self.process_manager.is_running(vpn_type)

    def wait_for_connection(
        self, vpn_type: VPNType, log_path: Path, on_tick: Optional[Callable] = None
    ) -> ConnectionResult:
        """Wait for VPN to connect with polling."""
        started = False
        for _ in range(int(self.TIMEOUT / 0.1)):
            if on_tick:
                on_tick()
            if log_path.exists():
                result = self.process_manager.check_status(log_path)
                if result:
                    return result
                started = True
            if started and not self.is_connected(vpn_type):
                import time

                time.sleep(0.5)
                return (
                    self.process_manager.check_status(log_path)
                    or ConnectionResult.PROCESS_DIED
                )
            import time

            time.sleep(0.1)
        return ConnectionResult.TIMEOUT

    def has_errors(self, log_path: Path) -> bool:
        return self.process_manager.has_errors(log_path)

    def cleanup(self, log_path: Path) -> None:
        self.process_manager.cleanup(log_path)
