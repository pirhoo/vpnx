"""OpenVPN management interface client."""

import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ManagementState(Enum):
    """OpenVPN management interface states."""

    CONNECTING = "CONNECTING"
    WAIT = "WAIT"
    AUTH = "AUTH"
    GET_CONFIG = "GET_CONFIG"
    ASSIGN_IP = "ASSIGN_IP"
    ADD_ROUTES = "ADD_ROUTES"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    EXITING = "EXITING"
    RESOLVE = "RESOLVE"
    TCP_CONNECT = "TCP_CONNECT"


@dataclass
class ManagementEvent:
    """Parsed event from management interface."""

    timestamp: int
    state: ManagementState
    description: str
    local_ip: str = ""
    remote_ip: str = ""


@dataclass
class Bytecount:
    """Bandwidth data from management interface."""

    bytes_in: int
    bytes_out: int


class ManagementClient:
    """TCP client for OpenVPN management interface."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7505):
        self.host = host
        self.port = port
        self._socket: Optional[socket.socket] = None
        self._buffer: str = ""
        self._last_bytecount: Optional[Bytecount] = None

    def connect(self, max_retries: int = 10, initial_delay: float = 0.1) -> bool:
        """Connect to management interface with retry logic."""
        delay = initial_delay
        for _ in range(max_retries):
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.connect((self.host, self.port))
                self._socket.setblocking(False)
                return True
            except (ConnectionRefusedError, OSError):
                if self._socket:
                    self._socket.close()
                    self._socket = None
                time.sleep(delay)
                delay = min(delay * 2, 1.0)
        return False

    def disconnect(self) -> None:
        """Close socket connection."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._buffer = ""

    def send_command(self, cmd: str) -> None:
        """Send command to management interface."""
        if self._socket:
            try:
                self._socket.sendall(f"{cmd}\n".encode("utf-8"))
            except OSError:
                pass

    def read_events(self) -> List[ManagementEvent]:
        """Non-blocking read of pending events."""
        if not self._socket:
            return []

        try:
            data = self._socket.recv(4096).decode("utf-8")
            self._buffer += data
        except BlockingIOError:
            pass
        except OSError:
            return []

        events = []
        lines = self._buffer.split("\n")
        self._buffer = lines[-1]

        for line in lines[:-1]:
            if line.startswith(">STATE:"):
                event = self._parse_state_line(line)
                if event:
                    events.append(event)
            elif line.startswith(">BYTECOUNT:"):
                bytecount = self._parse_bytecount_line(line)
                if bytecount:
                    self._last_bytecount = bytecount

        return events

    def _parse_bytecount_line(self, line: str) -> Optional[Bytecount]:
        """Parse >BYTECOUNT:<bytes_in>,<bytes_out> format."""
        try:
            content = line[11:]  # Remove ">BYTECOUNT:"
            parts = content.split(",")
            if len(parts) < 2:
                return None
            return Bytecount(bytes_in=int(parts[0]), bytes_out=int(parts[1]))
        except (ValueError, IndexError):
            return None

    def get_bytecount(self) -> Optional[Bytecount]:
        """Get the last received bytecount."""
        return self._last_bytecount

    def _parse_state_line(self, line: str) -> Optional[ManagementEvent]:
        """Parse >STATE:<timestamp>,<state>,<desc>,... format."""
        try:
            content = line[7:]  # Remove ">STATE:"
            parts = content.split(",")
            if len(parts) < 3:
                return None

            timestamp = int(parts[0])
            state_str = parts[1]
            description = parts[2]

            try:
                state = ManagementState(state_str)
            except ValueError:
                return None

            local_ip = parts[3] if len(parts) > 3 else ""
            remote_ip = parts[4] if len(parts) > 4 else ""

            return ManagementEvent(
                timestamp=timestamp,
                state=state,
                description=description,
                local_ip=local_ip,
                remote_ip=remote_ip,
            )
        except (ValueError, IndexError):
            return None

    @property
    def is_connected(self) -> bool:
        """Check if socket is connected."""
        return self._socket is not None
