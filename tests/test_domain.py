#!/usr/bin/env python3
"""Tests for domain layer."""

import unittest


from vpnx.domain.entities import BandwidthStats, VPNConnection, VPNState
from vpnx.domain.value_objects import ConnectionResult, Credentials, Status, VPNType


class TestStatus(unittest.TestCase):
    """Tests for Status enum."""

    def test_all_statuses_exist(self):
        self.assertEqual(len(Status), 4)
        self.assertIn(Status.DISCONNECTED, Status)
        self.assertIn(Status.WAITING, Status)
        self.assertIn(Status.CONNECTING, Status)
        self.assertIn(Status.CONNECTED, Status)

    def test_status_values(self):
        self.assertEqual(Status.DISCONNECTED.value, "disconnected")
        self.assertEqual(Status.CONNECTED.value, "connected")


class TestConnectionResult(unittest.TestCase):
    """Tests for ConnectionResult enum."""

    def test_all_results_exist(self):
        self.assertEqual(len(ConnectionResult), 4)

    def test_result_values(self):
        self.assertEqual(ConnectionResult.CONNECTED.value, "connected")
        self.assertEqual(ConnectionResult.AUTH_FAILED.value, "auth_failed")
        self.assertEqual(ConnectionResult.TIMEOUT.value, "timeout")
        self.assertEqual(ConnectionResult.PROCESS_DIED.value, "process_died")


class TestVPNType(unittest.TestCase):
    """Tests for VPNType value object."""

    def test_create_vpn_type(self):
        vpn = VPNType("ext")
        self.assertEqual(vpn.name, "EXT")

    def test_uppercase_conversion(self):
        vpn = VPNType("int")
        self.assertEqual(vpn.name, "INT")

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            VPNType("")

    def test_config_filename(self):
        vpn = VPNType("ext")
        self.assertEqual(vpn.config_filename, "client-EXT.ovpn")

    def test_log_prefix(self):
        vpn = VPNType("INT")
        self.assertEqual(vpn.log_prefix, "openvpn-int")

    def test_str_representation(self):
        vpn = VPNType("ext")
        self.assertEqual(str(vpn), "EXT")

    def test_immutability(self):
        vpn = VPNType("ext")
        with self.assertRaises(AttributeError):
            vpn.name = "INT"

    def test_equality(self):
        vpn1 = VPNType("ext")
        vpn2 = VPNType("EXT")
        self.assertEqual(vpn1, vpn2)

    def test_hashable(self):
        vpn = VPNType("ext")
        d = {vpn: "value"}
        self.assertEqual(d[VPNType("EXT")], "value")


class TestCredentials(unittest.TestCase):
    """Tests for Credentials value object."""

    def test_create_credentials(self):
        creds = Credentials("user", "pass")
        self.assertEqual(creds.username, "user")
        self.assertEqual(creds.password, "pass")
        self.assertEqual(creds.otp, "")

    def test_create_with_otp(self):
        creds = Credentials("user", "pass", "123456")
        self.assertEqual(creds.otp, "123456")

    def test_empty_username_raises(self):
        with self.assertRaises(ValueError):
            Credentials("", "pass")

    def test_empty_password_raises(self):
        with self.assertRaises(ValueError):
            Credentials("user", "")

    def test_auth_string_without_otp(self):
        creds = Credentials("user", "pass")
        self.assertEqual(creds.auth_string, "user\npass")

    def test_auth_string_with_otp(self):
        creds = Credentials("user", "pass", "123456")
        self.assertEqual(creds.auth_string, "user\npass123456")

    def test_with_otp_returns_new_instance(self):
        creds = Credentials("user", "pass")
        new_creds = creds.with_otp("123456")
        self.assertEqual(new_creds.otp, "123456")
        self.assertEqual(creds.otp, "")  # Original unchanged

    def test_immutability(self):
        creds = Credentials("user", "pass")
        with self.assertRaises(AttributeError):
            creds.username = "other"


class TestVPNState(unittest.TestCase):
    """Tests for VPNState entity."""

    def test_default_state(self):
        state = VPNState()
        # Uninitialized VPNs return defaults
        self.assertEqual(state.get_status(VPNType("PROD")), Status.DISCONNECTED)
        self.assertEqual(state.get_log(VPNType("PROD")), "")
        self.assertEqual(state.spinner_frame, 0)
        self.assertEqual(state.prompt, "")

    def test_set_status(self):
        state = VPNState()
        state.set_status(VPNType("PROD"), Status.CONNECTED)
        self.assertEqual(state.get_status(VPNType("PROD")), Status.CONNECTED)

    def test_set_log(self):
        state = VPNState()
        state.set_log(VPNType("PROD"), "/tmp/prod.log")
        self.assertEqual(state.get_log(VPNType("PROD")), "/tmp/prod.log")

    def test_get_bandwidth(self):
        state = VPNState()
        bw = state.get_bandwidth(VPNType("PROD"))
        self.assertEqual(bw.total_in, 0)
        self.assertEqual(bw.total_out, 0)

    def test_initialize(self):
        state = VPNState()
        state.initialize(["PROD", "DEV"])
        self.assertEqual(state.get_status(VPNType("PROD")), Status.DISCONNECTED)
        self.assertEqual(state.get_status(VPNType("DEV")), Status.DISCONNECTED)

    def test_advance_spinner(self):
        state = VPNState()
        self.assertEqual(state.spinner_frame, 0)
        state.advance_spinner()
        self.assertEqual(state.spinner_frame, 1)
        state.advance_spinner()
        self.assertEqual(state.spinner_frame, 2)


class TestVPNConnection(unittest.TestCase):
    """Tests for VPNConnection entity."""

    def test_default_connection(self):
        conn = VPNConnection(VPNType("PROD"))
        self.assertEqual(conn.vpn_type.name, "PROD")
        self.assertEqual(conn.status, Status.DISCONNECTED)
        self.assertIsNone(conn.log_path)
        self.assertIsNone(conn.pid)

    def test_is_active_disconnected(self):
        conn = VPNConnection(VPNType("PROD"))
        self.assertFalse(conn.is_active())

    def test_is_active_connecting(self):
        conn = VPNConnection(VPNType("PROD"), Status.CONNECTING)
        self.assertTrue(conn.is_active())

    def test_is_active_connected(self):
        conn = VPNConnection(VPNType("PROD"), Status.CONNECTED)
        self.assertTrue(conn.is_active())

    def test_is_active_waiting(self):
        conn = VPNConnection(VPNType("PROD"), Status.WAITING)
        self.assertFalse(conn.is_active())


class TestBandwidthStats(unittest.TestCase):
    """Tests for BandwidthStats entity."""

    def test_default_values(self):
        stats = BandwidthStats()
        self.assertEqual(stats.total_in, 0)
        self.assertEqual(stats.total_out, 0)
        self.assertEqual(stats.rate_in, 0.0)
        self.assertEqual(stats.rate_out, 0.0)
        self.assertEqual(stats.history_in, [])
        self.assertEqual(stats.history_out, [])

    def test_first_update_sets_totals(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        self.assertEqual(stats.total_in, 1000)
        self.assertEqual(stats.total_out, 500)
        # First update doesn't calculate rate (no delta)
        self.assertEqual(stats.rate_in, 0.0)
        self.assertEqual(stats.rate_out, 0.0)

    def test_second_update_calculates_rate(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 1.0)
        self.assertEqual(stats.rate_in, 1000.0)  # (2000-1000)/1.0
        self.assertEqual(stats.rate_out, 500.0)  # (1000-500)/1.0

    def test_rate_with_different_interval(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 2.0)
        self.assertEqual(stats.rate_in, 500.0)  # (2000-1000)/2.0
        self.assertEqual(stats.rate_out, 250.0)  # (1000-500)/2.0

    def test_history_accumulates_after_interval(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        # Accumulate for 10 seconds (HISTORY_INTERVAL)
        stats.update(2000, 1000, 10.0)
        self.assertEqual(len(stats.history_in), 1)
        self.assertEqual(len(stats.history_out), 1)
        # Average rate over 10 seconds: 1000 bytes / 10 sec
        self.assertAlmostEqual(stats.history_in[0], 1000 / 10, places=2)

    def test_history_not_added_before_interval(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        # Only 5 seconds elapsed (less than HISTORY_INTERVAL of 10s)
        stats.update(2000, 1000, 5.0)
        self.assertEqual(len(stats.history_in), 0)
        self.assertEqual(len(stats.history_out), 0)

    def test_history_max_length(self):
        stats = BandwidthStats()
        stats.update(100, 50, 1.0)
        # Add MAX_HISTORY + 5 intervals (each >= HISTORY_INTERVAL of 10s)
        for i in range(stats.MAX_HISTORY + 5):
            stats.update(100 * (i + 2), 50 * (i + 2), 10.0)
        self.assertEqual(len(stats.history_in), stats.MAX_HISTORY)
        self.assertEqual(len(stats.history_out), stats.MAX_HISTORY)

    def test_zero_interval_skips_rate_calculation(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 0.0)
        # Rate should remain 0 since interval is 0
        self.assertEqual(stats.rate_in, 0.0)
        # But totals are updated
        self.assertEqual(stats.total_in, 2000)

    def test_accumulator_resets_after_history_add(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 10.0)  # First history point
        stats.update(3000, 1500, 10.0)  # Second history point
        self.assertEqual(len(stats.history_in), 2)

    def test_rate_preserved_when_bytes_unchanged(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 5.0)  # Rate = 200 B/s
        self.assertEqual(stats.rate_in, 200.0)
        # Same bytes, different interval - rate should be preserved
        stats.update(2000, 1000, 1.0)
        self.assertEqual(stats.rate_in, 200.0)  # Still 200, not 0

    def test_no_update_when_bytes_unchanged(self):
        stats = BandwidthStats()
        stats.update(1000, 500, 1.0)
        stats.update(2000, 1000, 10.0)
        self.assertEqual(len(stats.history_in), 1)
        # Same bytes - should not add to history
        stats.update(2000, 1000, 10.0)
        self.assertEqual(len(stats.history_in), 1)  # Still 1


if __name__ == "__main__":
    unittest.main()
