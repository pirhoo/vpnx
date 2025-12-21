"""Domain entities - objects with identity and lifecycle."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from domain.value_objects import Status, VPNType


@dataclass
class VPNConnection:
    """Represents an active VPN connection."""

    vpn_type: VPNType
    status: Status = Status.DISCONNECTED
    log_path: Optional[Path] = None
    pid: Optional[int] = None

    def is_active(self) -> bool:
        return self.status in (Status.CONNECTING, Status.CONNECTED)


@dataclass
class VPNState:
    """UI state for displaying VPN connections."""

    ext_status: Status = Status.DISCONNECTED
    int_status: Status = Status.DISCONNECTED
    ext_log: str = ""
    int_log: str = ""
    spinner_frame: int = 0
    prompt: str = ""

    def set_status(self, vpn_type: VPNType, status: Status) -> None:
        if vpn_type.name == "EXT":
            self.ext_status = status
        else:
            self.int_status = status

    def set_log(self, vpn_type: VPNType, log_path: str) -> None:
        if vpn_type.name == "EXT":
            self.ext_log = log_path
        else:
            self.int_log = log_path

    def advance_spinner(self) -> None:
        self.spinner_frame += 1
