#!/usr/bin/env python3
"""Tests for domain layer."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from domain.value_objects import Status, VPNType, Credentials, ConnectionResult
from domain.entities import VPNState, VPNConnection


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
        self.assertEqual(state.ext_status, Status.DISCONNECTED)
        self.assertEqual(state.int_status, Status.DISCONNECTED)
        self.assertEqual(state.ext_log, "")
        self.assertEqual(state.int_log, "")
        self.assertEqual(state.spinner_frame, 0)
        self.assertEqual(state.prompt, "")

    def test_set_ext_status(self):
        state = VPNState()
        state.set_status(VPNType("EXT"), Status.CONNECTED)
        self.assertEqual(state.ext_status, Status.CONNECTED)

    def test_set_int_status(self):
        state = VPNState()
        state.set_status(VPNType("INT"), Status.CONNECTING)
        self.assertEqual(state.int_status, Status.CONNECTING)

    def test_set_ext_log(self):
        state = VPNState()
        state.set_log(VPNType("EXT"), "/tmp/ext.log")
        self.assertEqual(state.ext_log, "/tmp/ext.log")

    def test_set_int_log(self):
        state = VPNState()
        state.set_log(VPNType("INT"), "/tmp/int.log")
        self.assertEqual(state.int_log, "/tmp/int.log")

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
        conn = VPNConnection(VPNType("EXT"))
        self.assertEqual(conn.vpn_type.name, "EXT")
        self.assertEqual(conn.status, Status.DISCONNECTED)
        self.assertIsNone(conn.log_path)
        self.assertIsNone(conn.pid)

    def test_is_active_disconnected(self):
        conn = VPNConnection(VPNType("EXT"))
        self.assertFalse(conn.is_active())

    def test_is_active_connecting(self):
        conn = VPNConnection(VPNType("EXT"), Status.CONNECTING)
        self.assertTrue(conn.is_active())

    def test_is_active_connected(self):
        conn = VPNConnection(VPNType("EXT"), Status.CONNECTED)
        self.assertTrue(conn.is_active())

    def test_is_active_waiting(self):
        conn = VPNConnection(VPNType("EXT"), Status.WAITING)
        self.assertFalse(conn.is_active())


if __name__ == "__main__":
    unittest.main()
