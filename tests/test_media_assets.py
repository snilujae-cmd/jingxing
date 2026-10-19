"""Optional media must not make the data application unavailable."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.media import ASSET_FILES, asset_download, asset_path, render_image


class MediaAssetTests(unittest.TestCase):
    def test_delivered_images_are_decodable_and_project_relative(self):
        for key in ASSET_FILES:
            with self.subTest(key=key):
                self.assertTrue(asset_path(key).is_relative_to(ROOT))
                self.assertIsNotNone(asset_download(key))

    def test_assets_do_not_depend_on_current_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertIsNotNone(asset_download("routes"))
            finally:
                os.chdir(previous)

    def test_missing_and_corrupt_assets_are_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.jpg"
            with patch("utils.media.asset_path", return_value=path):
                self.assertIsNone(asset_download("routes"))
                path.write_bytes(b"not an image")
                self.assertIsNone(asset_download("routes"))

    def test_render_missing_image_only_emits_caption(self):
        fake = SimpleNamespace(caption=Mock(), image=Mock())
        with patch.dict(sys.modules, {"streamlit": fake}):
            with patch("utils.media.asset_download", return_value=None):
                self.assertFalse(render_image("routes", "线路图"))
        fake.caption.assert_called_once()
        fake.image.assert_not_called()


if __name__ == "__main__":
    unittest.main()
