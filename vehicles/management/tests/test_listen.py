from unittest import mock

from django.test import TestCase, override_settings
from django.core.management import call_command


class ListenTest(TestCase):
    @override_settings(NEW_VEHICLE_WEBHOOK_URL=None)
    def test_missing_setting(self):
        with self.assertRaises(AssertionError):
            call_command("listen")

    @override_settings(NEW_VEHICLE_WEBHOOK_URL="http://example.com")
    def test_listen(self):
        with (
            mock.patch(
                "vehicles.management.commands.listen.connection.cursor"
            ) as mock_cursor,
            mock.patch(
                "vehicles.management.commands.listen.requests.Session.post"
            ) as mock_post,
            mock.patch("vehicles.management.commands.listen.time.sleep") as mock_sleep,
        ):
            mock_cursor.return_value.__enter__.return_value.connection.notifies.return_value = [
                mock.Mock(payload="sndr-p420-kak"),
            ]

            call_command("listen")

        mock_post.assert_called_with(
            "http://example.com",
            json={
                "username": "bot",
                "content": "[sndr-p420-kak](https://bustimes.org/vehicles/sndr-p420-kak) <@813528710404898817>",
            },
            timeout=10,
        )

        mock_sleep.assert_called_with(5)
