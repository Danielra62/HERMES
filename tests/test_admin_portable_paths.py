import os
import unittest
from pathlib import Path
from unittest.mock import patch

from admin.core import clients, image_processing


class AdminPortablePathTests(unittest.TestCase):
    def test_frozen_admin_uses_data_directory_next_to_executable(self):
        executable = Path(r"C:\Portable\HermesAdmin\HermesAdmin.exe")
        with (
            patch.object(clients.sys, "frozen", True, create=True),
            patch.object(clients.sys, "executable", str(executable)),
        ):
            self.assertEqual(
                clients._directorio_datos(),
                executable.parent / "data",
            )
            self.assertFalse(clients._usar_mysql())

    def test_frozen_image_storage_defaults_to_persistent_data_folder(self):
        executable = Path(r"C:\Portable\HermesAdmin\HermesAdmin.exe")
        with (
            patch.object(image_processing.sys, "frozen", True, create=True),
            patch.object(image_processing.sys, "executable", str(executable)),
            patch.dict(os.environ, {"HERMES_STORAGE_DIR": ""}, clear=False),
        ):
            self.assertEqual(
                image_processing.directorio_almacenamiento(),
                executable.parent / "data" / "storage",
            )

    def test_frozen_relative_storage_override_is_resolved_next_to_executable(self):
        executable = Path(r"C:\Portable\HermesAdmin\HermesAdmin.exe")
        with (
            patch.object(image_processing.sys, "frozen", True, create=True),
            patch.object(image_processing.sys, "executable", str(executable)),
            patch.dict(
                os.environ,
                {"HERMES_STORAGE_DIR": r"other-data\images"},
                clear=False,
            ),
        ):
            self.assertEqual(
                image_processing.directorio_almacenamiento(),
                executable.parent / "other-data" / "images",
            )


if __name__ == "__main__":
    unittest.main()
