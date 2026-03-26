#!/usr/bin/env python3
"""Tests for application configuration."""

import os
import tempfile
import unittest
from pathlib import Path


from vpnx.infrastructure.app_config import AppConfig, VPNConfig
from vpnx.infrastructure.xdg import XDGPaths


class TestVPNConfig(unittest.TestCase):
    """Tests for VPNConfig dataclass."""

    def test_create_vpn_config(self):
        vpn = VPNConfig(
            name="EXT", display_name="External", config_path=Path("/etc/vpn/ext.ovpn")
        )
        self.assertEqual(vpn.name, "EXT")
        self.assertEqual(vpn.display_name, "External")
        self.assertEqual(vpn.config_path, Path("/etc/vpn/ext.ovpn"))
        self.assertFalse(vpn.needs_up_script)
        self.assertIsNone(vpn.tun_mtu)

    def test_create_with_up_script(self):
        vpn = VPNConfig(
            name="EXT",
            display_name="External",
            config_path=Path("/etc/vpn/ext.ovpn"),
            needs_up_script=True,
        )
        self.assertTrue(vpn.needs_up_script)

    def test_to_dict(self):
        vpn = VPNConfig(
            name="EXT",
            display_name="External",
            config_path=Path("/etc/vpn/ext.ovpn"),
            needs_up_script=True,
            tun_mtu=1400
        )
        data = vpn.to_dict()
        self.assertEqual(data["name"], "EXT")
        self.assertEqual(data["display"], "External")
        self.assertEqual(data["config_path"], "/etc/vpn/ext.ovpn")
        self.assertTrue(data["needs_up_script"])
        self.assertEqual(data["tun_mtu"], 1400)

    def test_from_dict(self):
        data = {
            "name": "ext",
            "display": "External",
            "config_path": "/etc/vpn/ext.ovpn",
            "needs_up_script": True,
            "tun_mtu": 1300,
        }
        vpn = VPNConfig.from_dict(data)
        self.assertEqual(vpn.name, "EXT")  # Uppercase
        self.assertEqual(vpn.display_name, "External")
        self.assertEqual(vpn.config_path, Path("/etc/vpn/ext.ovpn"))
        self.assertTrue(vpn.needs_up_script)
        self.assertEqual(vpn.tun_mtu, 1300)


class TestAppConfig(unittest.TestCase):
    """Tests for AppConfig dataclass."""

    def test_create_config(self):
        config = AppConfig(
            username="john",
            credentials_path=Path("/tmp/creds"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                )
            ],
        )
        self.assertEqual(config.username, "john")
        self.assertEqual(config.credentials_path, Path("/tmp/creds"))
        self.assertEqual(len(config.vpns), 1)

    def test_get_vpn_found(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                ),
                VPNConfig(
                    name="INT",
                    display_name="Internal",
                    config_path=Path("/etc/vpn/int.ovpn"),
                ),
            ],
        )
        vpn = config.get_vpn("ext")
        self.assertIsNotNone(vpn)
        self.assertEqual(vpn.name, "EXT")

    def test_get_vpn_case_insensitive(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                )
            ],
        )
        self.assertIsNotNone(config.get_vpn("ext"))
        self.assertIsNotNone(config.get_vpn("EXT"))
        self.assertIsNotNone(config.get_vpn("Ext"))

    def test_get_vpn_not_found(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                )
            ],
        )
        self.assertIsNone(config.get_vpn("PROD"))

    def test_vpn_names(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                ),
                VPNConfig(
                    name="INT",
                    display_name="Internal",
                    config_path=Path("/etc/vpn/int.ovpn"),
                ),
            ],
        )
        self.assertEqual(config.vpn_names(), ["EXT", "INT"])

    def test_add_vpn(self):
        config = AppConfig(
            username="", credentials_path=Path("/tmp"), up_script=None, vpns=[]
        )
        vpn = VPNConfig(
            name="EXT",
            display_name="External",
            config_path=Path("/etc/vpn/ext.ovpn"),
        )
        config.add_vpn(vpn)
        self.assertEqual(len(config.vpns), 1)
        self.assertEqual(config.vpns[0].name, "EXT")

    def test_add_vpn_replaces_existing(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="Old",
                    config_path=Path("/etc/vpn/old.ovpn"),
                )
            ],
        )
        new_vpn = VPNConfig(
            name="EXT",
            display_name="New",
            config_path=Path("/etc/vpn/new.ovpn"),
        )
        config.add_vpn(new_vpn)
        self.assertEqual(len(config.vpns), 1)
        self.assertEqual(config.vpns[0].display_name, "New")

    def test_remove_vpn(self):
        config = AppConfig(
            username="",
            credentials_path=Path("/tmp"),
            up_script=None,
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                )
            ],
        )
        result = config.remove_vpn("ext")
        self.assertTrue(result)
        self.assertEqual(len(config.vpns), 0)

    def test_remove_vpn_not_found(self):
        config = AppConfig(
            username="", credentials_path=Path("/tmp"), up_script=None, vpns=[]
        )
        result = config.remove_vpn("ext")
        self.assertFalse(result)

    def test_to_dict(self):
        config = AppConfig(
            username="john",
            credentials_path=Path("/tmp/creds"),
            up_script=Path("/etc/vpn/up.sh"),
            vpns=[
                VPNConfig(
                    name="EXT",
                    display_name="External",
                    config_path=Path("/etc/vpn/ext.ovpn"),
                )
            ],
        )
        data = config.to_dict()
        self.assertEqual(data["username"], "john")
        self.assertEqual(data["credentials_path"], "/tmp/creds")  # YAML key
        self.assertEqual(data["up_script"], "/etc/vpn/up.sh")
        self.assertEqual(len(data["vpns"]), 1)


class TestAppConfigSaveLoad(unittest.TestCase):
    """Tests for AppConfig save/load."""

    def test_save_and_load(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            config = AppConfig(
                username="john",
                credentials_path=Path("/tmp/creds"),
                up_script=None,
                vpns=[
                    VPNConfig(
                        name="EXT",
                        display_name="External",
                        config_path=Path("/etc/vpn/ext.ovpn"),
                        needs_up_script=True,
                    )
                ],
            )
            config.save(config_path)

            loaded = AppConfig.load(config_path)
            self.assertEqual(loaded.username, "john")
            self.assertEqual(loaded.credentials_path, Path("/tmp/creds"))
            self.assertEqual(len(loaded.vpns), 1)
            self.assertEqual(loaded.vpns[0].name, "EXT")
            self.assertTrue(loaded.vpns[0].needs_up_script)

    def test_save_and_load_with_tun_mtu(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = AppConfig(
                username="john",
                credentials_path=Path("/tmp/creds"),
                up_script=None,
                vpns=[
                    VPNConfig(
                        name="EXT",
                        display_name="External",
                        config_path=Path("/etc/vpn/ext.ovpn"),
                        tun_mtu=1400,
                    )
                ],
            )
            config.save(config_path)
            loaded = AppConfig.load(config_path)
            self.assertEqual(loaded.vpns[0].tun_mtu, 1400)

    def test_save_and_load_tun_mtu_none_not_written(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = AppConfig(
                username="john",
                credentials_path=Path("/tmp/creds"),
                up_script=None,
                vpns=[
                    VPNConfig(
                        name="EXT",
                        display_name="External",
                        config_path=Path("/etc/vpn/ext.ovpn"),
                    )
                ],
            )
            config.save(config_path)
            with open(config_path) as f:
                raw = yaml.safe_load(f)
            self.assertNotIn("tun_mtu", raw["vpns"][0])

    def test_empty_config(self):
        xdg = XDGPaths(
            config_home=Path("/tmp/config"),
            data_home=Path("/tmp/data"),
            cache_home=Path("/tmp/cache"),
        )
        config = AppConfig.empty(xdg)
        self.assertEqual(config.username, "")
        self.assertEqual(config.credentials_path, Path("/tmp/data/credentials"))
        self.assertEqual(len(config.vpns), 0)


class TestXDGPaths(unittest.TestCase):
    """Tests for XDGPaths."""

    def test_default_paths(self):
        xdg = XDGPaths.default()
        home = Path.home()
        self.assertEqual(xdg.config_home, home / ".config" / "vpnx")
        self.assertEqual(xdg.data_home, home / ".local" / "share" / "vpnx")
        self.assertEqual(xdg.cache_home, home / ".cache" / "vpnx")

    def test_config_file(self):
        xdg = XDGPaths(
            config_home=Path("/tmp/config"),
            data_home=Path("/tmp/data"),
            cache_home=Path("/tmp/cache"),
        )
        self.assertEqual(xdg.config_file, Path("/tmp/config/config.yaml"))

    def test_credentials_path(self):
        """Test credentials_path property."""
        xdg = XDGPaths(
            config_home=Path("/tmp/config"),
            data_home=Path("/tmp/data"),
            cache_home=Path("/tmp/cache"),
        )
        self.assertEqual(xdg.credentials_path, Path("/tmp/data/credentials"))

    def test_logs_dir(self):
        xdg = XDGPaths(
            config_home=Path("/tmp/config"),
            data_home=Path("/tmp/data"),
            cache_home=Path("/tmp/cache"),
        )
        self.assertEqual(xdg.logs_dir, Path("/tmp/cache/logs"))

    def test_ensure_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            xdg = XDGPaths(
                config_home=Path(tmpdir) / "config",
                data_home=Path(tmpdir) / "data",
                cache_home=Path(tmpdir) / "cache",
            )
            xdg.ensure_dirs()
            self.assertTrue(xdg.config_home.exists())
            self.assertTrue(xdg.data_home.exists())
            self.assertTrue(xdg.cache_home.exists())
            self.assertTrue(xdg.logs_dir.exists())

    def test_respects_xdg_env(self):
        orig_config = os.environ.get("XDG_CONFIG_HOME")
        orig_data = os.environ.get("XDG_DATA_HOME")
        orig_cache = os.environ.get("XDG_CACHE_HOME")

        try:
            os.environ["XDG_CONFIG_HOME"] = "/custom/config"
            os.environ["XDG_DATA_HOME"] = "/custom/data"
            os.environ["XDG_CACHE_HOME"] = "/custom/cache"

            xdg = XDGPaths.default()
            self.assertEqual(xdg.config_home, Path("/custom/config/vpnx"))
            self.assertEqual(xdg.data_home, Path("/custom/data/vpnx"))
            self.assertEqual(xdg.cache_home, Path("/custom/cache/vpnx"))
        finally:
            # Restore original values
            if orig_config is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = orig_config
            if orig_data is None:
                os.environ.pop("XDG_DATA_HOME", None)
            else:
                os.environ["XDG_DATA_HOME"] = orig_data
            if orig_cache is None:
                os.environ.pop("XDG_CACHE_HOME", None)
            else:
                os.environ["XDG_CACHE_HOME"] = orig_cache


if __name__ == "__main__":
    unittest.main()
