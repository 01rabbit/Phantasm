import os
import unittest
from unittest import mock

from src.phasmid.luks_layer import LuksConfig, LuksLayer, LuksMode


class LuksLayerDirectTests(unittest.TestCase):
    @mock.patch("src.phasmid.luks_layer.subprocess.run")
    @mock.patch(
        "src.phasmid.luks_layer.shutil.which", return_value="/usr/sbin/cryptsetup"
    )
    @mock.patch("src.phasmid.luks_layer.open", new_callable=mock.mock_open)
    @mock.patch("src.phasmid.luks_layer.os.makedirs")
    def test_mount_success_invokes_wrapper_and_sets_state_dir(
        self, _makedirs, _open_mock, _which_mock, run_mock
    ):
        run_mock.return_value = mock.Mock(returncode=0)
        layer = LuksLayer(
            LuksConfig(
                mode=LuksMode.FILE_CONTAINER,
                container_path="/opt/phasmid/luks.img",
                mount_point="/mnt/phasmid-vault",
            )
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            result = layer.mount("passphrase")
            state_dir = os.environ["PHASMID_STATE_DIR"]

        self.assertTrue(result.success)
        self.assertTrue(result.mounted)
        self.assertEqual(state_dir, "/mnt/phasmid-vault")
        run_mock.assert_called_once_with(
            [
                "sudo",
                layer.WRAPPER_PATH,
                "mount",
                "/opt/phasmid/luks.img",
                "/mnt/phasmid-vault",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("src.phasmid.luks_layer.subprocess.run")
    @mock.patch(
        "src.phasmid.luks_layer.shutil.which", return_value="/usr/sbin/cryptsetup"
    )
    @mock.patch("src.phasmid.luks_layer.open", new_callable=mock.mock_open)
    @mock.patch("src.phasmid.luks_layer.os.makedirs")
    def test_mount_nonzero_wrapper_return_reports_failure(
        self, _makedirs, _open_mock, _which_mock, run_mock
    ):
        run_mock.return_value = mock.Mock(returncode=1)
        layer = LuksLayer(LuksConfig(mode=LuksMode.FILE_CONTAINER))

        result = layer.mount("passphrase")

        self.assertFalse(result.success)
        self.assertFalse(result.mounted)
        self.assertEqual(result.error_message, "mount wrapper failed")

    @mock.patch("src.phasmid.luks_layer.shutil.which", return_value=None)
    def test_mount_missing_cryptsetup_reports_unavailable(self, _which_mock):
        layer = LuksLayer(LuksConfig(mode=LuksMode.FILE_CONTAINER))

        result = layer.mount("passphrase")

        self.assertFalse(result.success)
        self.assertFalse(result.mounted)
        self.assertEqual(result.error_message, "cryptsetup not available")


if __name__ == "__main__":
    unittest.main()
