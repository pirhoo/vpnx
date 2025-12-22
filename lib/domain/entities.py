"""Domain entities - objects with identity and lifecycle."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from domain.value_objects import Status, VPNType


@dataclass
class BandwidthStats:
    """Bandwidth statistics for a VPN connection."""

    total_in: int = 0
    total_out: int = 0
    rate_in: float = 0.0
    rate_out: float = 0.0
    history_in: List[float] = field(default_factory=list)
    history_out: List[float] = field(default_factory=list)

    # Accumulator for history interval
    _interval_bytes_in: int = field(default=0, repr=False)
    _interval_bytes_out: int = field(default=0, repr=False)
    _interval_duration: float = field(default=0.0, repr=False)

    MAX_HISTORY = 20
    HISTORY_INTERVAL = 60.0  # seconds per history point (1 minute)

    def update(self, bytes_in: int, bytes_out: int, interval: float) -> None:
        """Update stats with new bytecount data."""
        # Only update rate when bytes actually change (OpenVPN sends updates every ~5s)
        if bytes_in == self.total_in and bytes_out == self.total_out:
            return  # No change, keep previous rate

        if interval > 0 and self.total_in > 0:
            # Calculate rate from delta
            delta_in = bytes_in - self.total_in
            delta_out = bytes_out - self.total_out
            self.rate_in = delta_in / interval
            self.rate_out = delta_out / interval

            # Accumulate for history
            self._interval_bytes_in += delta_in
            self._interval_bytes_out += delta_out
            self._interval_duration += interval

            # Add to history when interval completes
            if self._interval_duration >= self.HISTORY_INTERVAL:
                avg_in = self._interval_bytes_in / self._interval_duration
                avg_out = self._interval_bytes_out / self._interval_duration
                self.history_in.append(avg_in)
                self.history_out.append(avg_out)

                if len(self.history_in) > self.MAX_HISTORY:
                    self.history_in.pop(0)
                if len(self.history_out) > self.MAX_HISTORY:
                    self.history_out.pop(0)

                # Reset accumulator
                self._interval_bytes_in = 0
                self._interval_bytes_out = 0
                self._interval_duration = 0.0

        self.total_in = bytes_in
        self.total_out = bytes_out


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
    ext_bandwidth: BandwidthStats = field(default_factory=BandwidthStats)
    int_bandwidth: BandwidthStats = field(default_factory=BandwidthStats)

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

    def get_bandwidth(self, vpn_type: VPNType) -> BandwidthStats:
        if vpn_type.name == "EXT":
            return self.ext_bandwidth
        return self.int_bandwidth

    def advance_spinner(self) -> None:
        self.spinner_frame += 1
