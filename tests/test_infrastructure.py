#!/usr/bin/env python3
"""Tests for infrastructure layer."""

import os
import tempfile
import unittest
from pathlib import Path


from unittest.mock import Mock, patch

from vpnx.domain.value_objects import VPNType
from vpnx.infrastructure.log_reader import LogReader
from vpnx.infrastructure.password_store import GPGPasswordStore
from vpnx.infrastructure.process import CommandResult, CommandRunner
from vpnx.infrastructure.vpn_repository import FileVPNRepository


class TestCommandResult(unittest.TestCase):
    """Tests for CommandResult."""

    def test_success_true_on_zero_returncode(self):
        result = CommandResult(0, "output", "")
        self.assertTrue(result.success)

    def test_success_false_on_nonzero_returncode(self):
        result = CommandResult(1, "", "error")
        self.assertFalse(result.success)

    def test_success_false_on_negative_returncode(self):
        result = CommandResult(-1, "", "")
        self.assertFalse(result.success)


class TestCommandRunner(unittest.TestCase):
    """Tests for CommandRunner."""

    def setUp(self):
        self.runner = CommandRunner()

    def test_run_echo(self):
        result = self.runner.run(["echo", "hello"])
        self.assertTrue(result.success)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_run_false_command(self):
        result = self.runner.run(["false"])
        self.assertFalse(result.success)

    def test_run_nonexistent_command(self):
        result = self.runner.run(["nonexistent_command_xyz"])
        self.assertFalse(result.success)
        self.assertIn("not found", result.stderr)

    def test_run_with_timeout(self):
        result = self.runner.run(["sleep", "0.1"], timeout=5)
        self.assertTrue(result.success)

    def test_exists_true(self):
        self.assertTrue(self.runner.exists("echo"))

    def test_exists_false(self):
        self.assertFalse(self.runner.exists("nonexistent_command_xyz"))

    def test_run_captures_stderr(self):
        result = self.runner.run(["sh", "-c", "echo error >&2"])
        self.assertIn("error", result.stderr)


class TestFileVPNRepository(unittest.TestCase):
    """Tests for FileVPNRepository."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo = FileVPNRepository(Path(self.temp_dir))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_list_available_empty(self):
        vpns = self.repo.list_available()
        self.assertEqual(vpns, [])

    def test_list_available_with_configs(self):
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        Path(self.temp_dir, "client-INT.ovpn").touch()
        vpns = self.repo.list_available()
        names = [v.name for v in vpns]
        self.assertIn("EXT", names)
        self.assertIn("INT", names)

    def test_list_available_ignores_non_matching(self):
        Path(self.temp_dir, "other.ovpn").touch()
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        vpns = self.repo.list_available()
        self.assertEqual(len(vpns), 1)
        self.assertEqual(vpns[0].name, "EXT")

    def test_list_available_nonexistent_dir(self):
        repo = FileVPNRepository(Path("/nonexistent/path"))
        self.assertEqual(repo.list_available(), [])

    def test_exists_true(self):
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        self.assertTrue(self.repo.exists(VPNType("EXT")))

    def test_exists_false(self):
        self.assertFalse(self.repo.exists(VPNType("EXT")))

    def test_config_path(self):
        path = self.repo.config_path(VPNType("EXT"))
        self.assertEqual(path.name, "client-EXT.ovpn")


class TestLogReader(unittest.TestCase):
    """Tests for LogReader."""

    def setUp(self):
        self.reader = LogReader()
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)

    def tearDown(self):
        os.unlink(self.temp_file.name)

    def test_read_tail_empty_file(self):
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, [])

    def test_read_tail_single_line(self):
        self.temp_file.write("hello\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["hello"])

    def test_read_tail_multiple_lines(self):
        self.temp_file.write("line1\nline2\nline3\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["line1", "line2", "line3"])

    def test_read_tail_limits_lines(self):
        self.temp_file.write("line1\nline2\nline3\nline4\nline5\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 2)
        self.assertEqual(lines, ["line4", "line5"])

    def test_read_tail_nonexistent_file(self):
        lines = self.reader.read_tail("/nonexistent/file", 10)
        self.assertEqual(lines, [])

    def test_read_tail_empty_path(self):
        lines = self.reader.read_tail("", 10)
        self.assertEqual(lines, [])

    def test_read_tail_strips_carriage_return(self):
        self.temp_file.write("line1\r\nline2\r\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["line1", "line2"])

    def test_read_tail_with_offset(self):
        self.temp_file.write("line1\nline2\nline3\nline4\nline5\n")
        self.temp_file.close()
        # Offset 2 means skip last 2 lines
        lines = self.reader.read_tail(self.temp_file.name, 2, offset=2)
        self.assertEqual(lines, ["line2", "line3"])

    def test_read_tail_with_offset_exceeds_lines(self):
        self.temp_file.write("line1\nline2\n")
        self.temp_file.close()
        # Offset exceeds available lines
        lines = self.reader.read_tail(self.temp_file.name, 2, offset=10)
        self.assertEqual(lines, ["line1", "line2"])

    def test_count_lines_empty_file(self):
        self.temp_file.close()
        count = self.reader.count_lines(self.temp_file.name)
        self.assertEqual(count, 0)

    def test_count_lines_single_line(self):
        self.temp_file.write("hello\n")
        self.temp_file.close()
        count = self.reader.count_lines(self.temp_file.name)
        self.assertEqual(count, 1)

    def test_count_lines_multiple_lines(self):
        self.temp_file.write("line1\nline2\nline3\n")
        self.temp_file.close()
        count = self.reader.count_lines(self.temp_file.name)
        self.assertEqual(count, 3)

    def test_count_lines_nonexistent_file(self):
        count = self.reader.count_lines("/nonexistent/file")
        self.assertEqual(count, 0)

    def test_count_lines_empty_path(self):
        count = self.reader.count_lines("")
        self.assertEqual(count, 0)


class TestGPGPasswordStore(unittest.TestCase):
    """Tests for GPGPasswordStore."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir) / "credentials"
        self.store = GPGPasswordStore(self.base_path)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_init_sets_paths(self):
        self.assertEqual(self.store.password_file, Path(str(self.base_path) + ".gpg"))
        self.assertEqual(self.store.gpg_id_file, Path(str(self.base_path) + ".gpg-id"))

    def test_is_initialized_false_initially(self):
        self.assertFalse(self.store.is_initialized())

    def test_is_initialized_true_after_init(self):
        self.store.initialize("ABCD1234")
        self.assertTrue(self.store.is_initialized())

    def test_initialize_creates_gpg_id_file(self):
        self.store.initialize("ABCD1234")
        self.assertTrue(self.store.gpg_id_file.exists())
        self.assertEqual(self.store.gpg_id_file.read_text(), "ABCD1234\n")

    def test_initialize_strips_whitespace(self):
        self.store.initialize("  ABCD1234  \n")
        self.assertEqual(self.store.gpg_id_file.read_text(), "ABCD1234\n")

    def test_has_password_false_initially(self):
        self.assertFalse(self.store.has_password())

    def test_get_gpg_id_returns_none_when_not_initialized(self):
        self.assertIsNone(self.store.get_gpg_id())

    def test_get_gpg_id_returns_id_after_init(self):
        self.store.initialize("ABCD1234")
        self.assertEqual(self.store.get_gpg_id(), "ABCD1234")

    def test_get_password_returns_none_when_no_file(self):
        self.assertIsNone(self.store.get_password("user"))

    def test_store_password_fails_when_not_initialized(self):
        result = self.store.store_password("secret")
        self.assertFalse(result)

    @patch("subprocess.run")
    def test_get_password_calls_gpg_decrypt(self, mock_run):
        # Create password file
        self.store.password_file.touch()
        mock_run.return_value = Mock(returncode=0, stdout="secret_password")

        result = self.store.get_password("user")

        self.assertEqual(result, "secret_password")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("gpg", args)
        self.assertIn("--decrypt", args)

    @patch("subprocess.run")
    def test_get_password_returns_none_on_gpg_error(self, mock_run):
        self.store.password_file.touch()
        mock_run.return_value = Mock(returncode=1, stdout="")

        result = self.store.get_password("user")

        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_store_password_calls_gpg_encrypt(self, mock_run):
        self.store.initialize("ABCD1234")
        mock_run.return_value = Mock(returncode=0)

        result = self.store.store_password("secret")

        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("gpg", args)
        self.assertIn("--encrypt", args)
        self.assertIn("--recipient", args)
        self.assertIn("ABCD1234", args)

    @patch("subprocess.run")
    def test_store_password_returns_false_on_gpg_error(self, mock_run):
        self.store.initialize("ABCD1234")
        mock_run.return_value = Mock(returncode=1)

        result = self.store.store_password("secret")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
