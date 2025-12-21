"""Domain value objects - immutable objects defined by their attributes."""

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    """VPN connection status."""

    DISCONNECTED = "disconnected"
    WAITING = "waiting"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class ConnectionResult(Enum):
    """Result of a VPN connection attempt."""

    CONNECTED = "connected"
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"
    PROCESS_DIED = "process_died"


@dataclass(frozen=True)
class VPNType:
    """VPN type identifier (immutable)."""

    name: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("VPN type name cannot be empty")
        object.__setattr__(self, "name", self.name.upper())

    def __str__(self) -> str:
        return self.name

    @property
    def config_filename(self) -> str:
        return f"client-{self.name}.ovpn"

    @property
    def log_prefix(self) -> str:
        return f"openvpn-{self.name.lower()}"


@dataclass(frozen=True)
class Credentials:
    """User credentials (immutable)."""

    username: str
    password: str
    otp: str = ""

    def __post_init__(self):
        if not self.username:
            raise ValueError("Username cannot be empty")
        if not self.password:
            raise ValueError("Password cannot be empty")

    @property
    def auth_string(self) -> str:
        """Format credentials for OpenVPN auth-user-pass."""
        return f"{self.username}\n{self.password}{self.otp}"

    def with_otp(self, otp: str) -> "Credentials":
        """Return new Credentials with OTP added."""
        return Credentials(self.username, self.password, otp)
