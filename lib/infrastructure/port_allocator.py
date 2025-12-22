"""Port allocation for OpenVPN management interfaces."""

import socket
import threading
from typing import ClassVar, Set


class PortAllocator:
    """Allocate unique ports for management interfaces."""

    BASE_PORT = 7505
    MAX_PORTS = 100

    _allocated: ClassVar[Set[int]] = set()
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def allocate(cls) -> int:
        """Allocate next available port starting from BASE_PORT."""
        with cls._lock:
            for offset in range(cls.MAX_PORTS):
                port = cls.BASE_PORT + offset
                if port not in cls._allocated and not cls.is_port_in_use(port):
                    cls._allocated.add(port)
                    return port
            raise RuntimeError("No available ports for management interface")

    @classmethod
    def release(cls, port: int) -> None:
        """Release a previously allocated port."""
        with cls._lock:
            cls._allocated.discard(port)

    @classmethod
    def is_port_in_use(cls, port: int) -> bool:
        """Check if port is in use by attempting to bind."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return False
        except OSError:
            return True

    @classmethod
    def reset(cls) -> None:
        """Reset allocator state (for testing)."""
        with cls._lock:
            cls._allocated.clear()
