import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from admin import main


class AdminLauncherTests(unittest.TestCase):
    def test_browser_opens_only_after_local_health_check_succeeds(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with (
            patch(
                "admin.main.urllib.request.urlopen",
                side_effect=[URLError("starting"), response],
            ) as urlopen,
            patch("admin.main.webbrowser.open", return_value=True) as open_browser,
            patch("admin.main.time.sleep"),
        ):
            main._abrir_navegador_cuando_listo()

        self.assertEqual(urlopen.call_count, 2)
        open_browser.assert_called_once_with("http://127.0.0.1:8080")

    def test_browser_auto_open_is_enabled_only_for_frozen_app(self):
        with (
            patch.object(main.sys, "frozen", True, create=True),
            patch.object(main, "iniciar_listener_heartbeat"),
            patch.object(main, "iniciar_scheduler"),
            patch.object(main, "iniciar_worker_ordenes"),
            patch.object(main, "_iniciar_apertura_navegador") as start_browser,
            patch.object(main.app, "run"),
        ):
            main.main()

        start_browser.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
