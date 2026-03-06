"""Tests for OpenVPN management interface components."""

import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock


from vpnx.infrastructure.config_parser import ManagementConfig, OpenVPNConfigParser
from vpnx.infrastructure.management import (
    Bytecount,
    ManagementClient,
    ManagementEvent,
    ManagementState,
)
from vpnx.infrastructure.port_allocator import PortAllocator


class TestPortAllocator(unittest.TestCase):
    """Tests for PortAllocator."""

    def setUp(self):
        PortAllocator.reset()

    def tearDown(self):
        PortAllocator.reset()

    def test_allocate_returns_base_port_first(self):
        port = PortAllocator.allocate()
        self.assertEqual(port, PortAllocator.BASE_PORT)

    def test_allocate_increments_port(self):
        p1 = PortAllocator.allocate()
        p2 = PortAllocator.allocate()
        self.assertEqual(p2, p1 + 1)

    def test_release_allows_reuse(self):
        p1 = PortAllocator.allocate()
        PortAllocator.release(p1)
        p2 = PortAllocator.allocate()
        self.assertEqual(p1, p2)

    def test_release_nonexistent_port_no_error(self):
        PortAllocator.release(99999)  # Should not raise

    def test_reset_clears_allocations(self):
        PortAllocator.allocate()
        PortAllocator.allocate()
        PortAllocator.reset()
        port = PortAllocator.allocate()
        self.assertEqual(port, PortAllocator.BASE_PORT)

    def test_allocate_skips_in_use_ports(self):
        # Bind to base port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", PortAllocator.BASE_PORT))
            port = PortAllocator.allocate()
            self.assertEqual(port, PortAllocator.BASE_PORT + 1)

    def test_is_port_in_use_returns_true_for_bound_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", PortAllocator.BASE_PORT))
            self.assertTrue(PortAllocator.is_port_in_use(PortAllocator.BASE_PORT))

    def test_is_port_in_use_returns_false_for_free_port(self):
        # Use a high port unlikely to be in use
        self.assertFalse(PortAllocator.is_port_in_use(59999))

    def test_thread_safety(self):
        ports = []
        errors = []

        def allocate():
            try:
                port = PortAllocator.allocate()
                ports.append(port)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=allocate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(ports), 10)
        self.assertEqual(len(set(ports)), 10)  # All unique


class TestManagementConfig(unittest.TestCase):
    """Tests for ManagementConfig dataclass."""

    def test_create_enabled(self):
        config = ManagementConfig(enabled=True, host="127.0.0.1", port=7505)
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 7505)

    def test_create_disabled(self):
        config = ManagementConfig(enabled=False)
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "")
        self.assertEqual(config.port, 0)


class TestOpenVPNConfigParser(unittest.TestCase):
    """Tests for OpenVPNConfigParser."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_config(self, content: str) -> Path:
        path = Path(self.temp_dir) / "test.ovpn"
        path.write_text(content)
        return path

    def test_has_management_directive_true(self):
        config = self._create_config(
            "client\nmanagement 127.0.0.1 7505\nremote server 1194"
        )
        parser = OpenVPNConfigParser(config)
        self.assertTrue(parser.has_management_directive())

    def test_has_management_directive_false(self):
        config = self._create_config("client\nremote server 1194")
        parser = OpenVPNConfigParser(config)
        self.assertFalse(parser.has_management_directive())

    def test_has_management_directive_commented_out(self):
        config = self._create_config(
            "client\n# management 127.0.0.1 7505\nremote server 1194"
        )
        parser = OpenVPNConfigParser(config)
        self.assertFalse(parser.has_management_directive())

    def test_get_management_config_parses_host_port(self):
        config = self._create_config("management 192.168.1.1 8080")
        parser = OpenVPNConfigParser(config)
        mgmt = parser.get_management_config()
        self.assertTrue(mgmt.enabled)
        self.assertEqual(mgmt.host, "192.168.1.1")
        self.assertEqual(mgmt.port, 8080)

    def test_get_management_config_disabled(self):
        config = self._create_config("client\nremote server 1194")
        parser = OpenVPNConfigParser(config)
        mgmt = parser.get_management_config()
        self.assertFalse(mgmt.enabled)

    def test_get_management_config_with_whitespace(self):
        config = self._create_config("  management   127.0.0.1   7505  ")
        parser = OpenVPNConfigParser(config)
        mgmt = parser.get_management_config()
        self.assertTrue(mgmt.enabled)
        self.assertEqual(mgmt.host, "127.0.0.1")
        self.assertEqual(mgmt.port, 7505)

    def test_append_management_directive(self):
        config = self._create_config("client\nremote server 1194")
        parser = OpenVPNConfigParser(config)
        parser.append_management_directive("127.0.0.1", 7505)
        content = config.read_text()
        self.assertIn("management 127.0.0.1 7505", content)
        self.assertTrue(content.endswith("\n"))

    def test_append_preserves_existing_content(self):
        original = "client\nremote server 1194"
        config = self._create_config(original)
        parser = OpenVPNConfigParser(config)
        parser.append_management_directive("127.0.0.1", 7505)
        content = config.read_text()
        self.assertTrue(content.startswith(original))

    def test_append_adds_newline_if_missing(self):
        config = self._create_config("client")
        parser = OpenVPNConfigParser(config)
        parser.append_management_directive("127.0.0.1", 7505)
        content = config.read_text()
        self.assertEqual(content, "client\nmanagement 127.0.0.1 7505\n")


class TestManagementState(unittest.TestCase):
    """Tests for ManagementState enum."""

    def test_all_states_exist(self):
        states = [
            "CONNECTING",
            "WAIT",
            "AUTH",
            "GET_CONFIG",
            "ASSIGN_IP",
            "ADD_ROUTES",
            "CONNECTED",
            "RECONNECTING",
            "EXITING",
            "RESOLVE",
            "TCP_CONNECT",
        ]
        for state in states:
            self.assertEqual(ManagementState(state).value, state)

    def test_invalid_state_raises(self):
        with self.assertRaises(ValueError):
            ManagementState("INVALID")


class TestManagementEvent(unittest.TestCase):
    """Tests for ManagementEvent dataclass."""

    def test_create_event(self):
        event = ManagementEvent(
            timestamp=1234567890,
            state=ManagementState.CONNECTED,
            description="SUCCESS",
            local_ip="10.0.0.1",
            remote_ip="1.2.3.4",
        )
        self.assertEqual(event.timestamp, 1234567890)
        self.assertEqual(event.state, ManagementState.CONNECTED)
        self.assertEqual(event.description, "SUCCESS")
        self.assertEqual(event.local_ip, "10.0.0.1")
        self.assertEqual(event.remote_ip, "1.2.3.4")

    def test_default_values(self):
        event = ManagementEvent(
            timestamp=0, state=ManagementState.CONNECTING, description=""
        )
        self.assertEqual(event.local_ip, "")
        self.assertEqual(event.remote_ip, "")


class TestManagementClient(unittest.TestCase):
    """Tests for ManagementClient."""

    def test_init_defaults(self):
        client = ManagementClient()
        self.assertEqual(client.host, "127.0.0.1")
        self.assertEqual(client.port, 7505)
        self.assertFalse(client.is_connected)

    def test_init_custom(self):
        client = ManagementClient(host="192.168.1.1", port=8080)
        self.assertEqual(client.host, "192.168.1.1")
        self.assertEqual(client.port, 8080)

    def test_parse_state_line_connected(self):
        client = ManagementClient()
        line = ">STATE:1234567890,CONNECTED,SUCCESS,10.0.0.1,1.2.3.4"
        event = client._parse_state_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.timestamp, 1234567890)
        self.assertEqual(event.state, ManagementState.CONNECTED)
        self.assertEqual(event.description, "SUCCESS")
        self.assertEqual(event.local_ip, "10.0.0.1")
        self.assertEqual(event.remote_ip, "1.2.3.4")

    def test_parse_state_line_connecting(self):
        client = ManagementClient()
        line = ">STATE:1234567890,CONNECTING,,"
        event = client._parse_state_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, ManagementState.CONNECTING)

    def test_parse_state_line_minimal(self):
        client = ManagementClient()
        line = ">STATE:1234567890,AUTH,auth"
        event = client._parse_state_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, ManagementState.AUTH)
        self.assertEqual(event.local_ip, "")

    def test_parse_state_line_invalid_format(self):
        client = ManagementClient()
        self.assertIsNone(client._parse_state_line("not a state line"))
        self.assertIsNone(client._parse_state_line(">STATE:invalid"))
        self.assertIsNone(client._parse_state_line(">STATE:123,UNKNOWN,desc"))

    def test_parse_state_line_with_extra_fields(self):
        client = ManagementClient()
        line = ">STATE:1234567890,CONNECTED,SUCCESS,10.0.0.1,1.2.3.4,extra,fields"
        event = client._parse_state_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(event.state, ManagementState.CONNECTED)

    def test_disconnect_when_not_connected(self):
        client = ManagementClient()
        client.disconnect()  # Should not raise

    def test_send_command_when_not_connected(self):
        client = ManagementClient()
        client.send_command("state on")  # Should not raise

    def test_read_events_when_not_connected(self):
        client = ManagementClient()
        events = client.read_events()
        self.assertEqual(events, [])


class TestManagementClientIntegration(unittest.TestCase):
    """Integration tests for ManagementClient with mock server."""

    def test_connect_to_server(self):
        # Start a simple server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]
        server.listen(1)

        def accept_connection():
            conn, _ = server.accept()
            conn.close()

        thread = threading.Thread(target=accept_connection)
        thread.start()

        client = ManagementClient(port=port)
        result = client.connect(max_retries=3, initial_delay=0.01)
        self.assertTrue(result)
        self.assertTrue(client.is_connected)
        client.disconnect()
        self.assertFalse(client.is_connected)

        thread.join()
        server.close()

    def test_connect_retry_on_failure(self):
        client = ManagementClient(port=59998)  # Port not listening
        result = client.connect(max_retries=2, initial_delay=0.01)
        self.assertFalse(result)
        self.assertFalse(client.is_connected)


class TestBytecount(unittest.TestCase):
    """Tests for Bytecount dataclass."""

    def test_create_bytecount(self):
        bc = Bytecount(bytes_in=1000, bytes_out=500)
        self.assertEqual(bc.bytes_in, 1000)
        self.assertEqual(bc.bytes_out, 500)


class TestManagementClientBytecount(unittest.TestCase):
    """Tests for bytecount parsing in ManagementClient."""

    def test_parse_bytecount_line_valid(self):
        client = ManagementClient()
        bc = client._parse_bytecount_line(">BYTECOUNT:12345,6789")
        self.assertIsNotNone(bc)
        self.assertEqual(bc.bytes_in, 12345)
        self.assertEqual(bc.bytes_out, 6789)

    def test_parse_bytecount_line_large_values(self):
        client = ManagementClient()
        bc = client._parse_bytecount_line(">BYTECOUNT:1234567890,9876543210")
        self.assertIsNotNone(bc)
        self.assertEqual(bc.bytes_in, 1234567890)
        self.assertEqual(bc.bytes_out, 9876543210)

    def test_parse_bytecount_line_invalid(self):
        client = ManagementClient()
        self.assertIsNone(client._parse_bytecount_line("not a bytecount"))
        self.assertIsNone(client._parse_bytecount_line(">BYTECOUNT:invalid"))
        self.assertIsNone(client._parse_bytecount_line(">BYTECOUNT:123"))

    def test_get_bytecount_initial_none(self):
        client = ManagementClient()
        self.assertIsNone(client.get_bytecount())

    def test_bytecount_updated_on_read(self):
        client = ManagementClient()
        # Manually set buffer with bytecount line
        client._buffer = ">BYTECOUNT:1000,500\n"
        client._socket = Mock()
        client._socket.recv.side_effect = BlockingIOError
        client.read_events()
        bc = client.get_bytecount()
        self.assertIsNotNone(bc)
        self.assertEqual(bc.bytes_in, 1000)
        self.assertEqual(bc.bytes_out, 500)


if __name__ == "__main__":
    unittest.main()
