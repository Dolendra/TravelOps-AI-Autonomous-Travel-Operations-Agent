import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

# Force test database file before any other imports
os.environ["DATABASE_URL"] = "sqlite:///test_travelops.db"

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.maps import MapsService
from backend.services.weather import WeatherService
from backend.services.notification import NotificationGateway


class TestIntegrations(unittest.TestCase):

    def setUp(self):
        # Clear environment variables before each test
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    # --- MapsService Tests ---

    @patch("urllib.request.urlopen")
    def test_maps_service_api_success(self, mock_urlopen):
        # Mock Google Maps API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "OK",
            "rows": [{
                "elements": [{
                    "status": "OK",
                    "distance": {"text": "550 km"},
                    "duration": {"text": "8h 15m"}
                }]
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Set API Key in env
        os.environ["GOOGLE_MAPS_API_KEY"] = "fake-key"

        res = MapsService.get_route_details("Bangalore", "Hyderabad")
        self.assertTrue(res["success"])
        self.assertEqual(res["distance"], "550 km")
        self.assertEqual(res["duration"], "8h 15m")
        self.assertEqual(res["source"], "Google Maps API")

    def test_maps_service_fallback(self):
        # No API key -> should use Haversine fallback
        res = MapsService.get_route_details("Bangalore", "Hyderabad")
        self.assertTrue(res["success"])
        self.assertEqual(res["source"], "Haversine Geodistance Model")
        self.assertIn("km", res["distance"])

        # Unknown city fallback
        res_unknown = MapsService.get_route_details("UnknownCityA", "UnknownCityB")
        self.assertTrue(res_unknown["success"])
        self.assertEqual(res_unknown["source"], "Default Route Approximation")
        self.assertEqual(res_unknown["distance"], "580 km")

    # --- WeatherService Tests ---

    @patch("urllib.request.urlopen")
    def test_weather_service_api_success(self, mock_urlopen):
        # Mock Open-Meteo API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "current_weather": {
                "temperature": 27.8,
                "weathercode": 3
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = WeatherService.get_weather_forecast("Bangalore", "2026-07-01")
        self.assertTrue(res["success"])
        self.assertEqual(res["temperature"], "27.8°C")
        self.assertEqual(res["condition"], "Overcast")
        self.assertEqual(res["source"], "Open-Meteo API")

    @patch("urllib.request.urlopen")
    def test_weather_service_api_failure_fallback(self, mock_urlopen):
        # Open-Meteo raises exception -> should use mock fallback
        mock_urlopen.side_effect = Exception("API offline")

        res = WeatherService.get_weather_forecast("Bangalore", "2026-07-01")
        self.assertTrue(res["success"])
        self.assertEqual(res["source"], "Mock Forecast Database")
        self.assertEqual(res["temperature"], "26°C")
        self.assertEqual(res["condition"], "Partly cloudy")

    # --- NotificationGateway Tests ---

    @patch("smtplib.SMTP")
    def test_notification_email_smtp_587(self, mock_smtp):
        # Set SMTP variables
        os.environ["SMTP_SERVER"] = "smtp.mail.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_USERNAME"] = "user"
        os.environ["SMTP_PASSWORD"] = "pass"

        server_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server_instance

        res = NotificationGateway.send_email("passenger@test.com", "Test Subject", "Test Body")
        self.assertTrue(res)
        server_instance.starttls.assert_called_once()
        server_instance.login.assert_called_with("user", "pass")
        server_instance.sendmail.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_notification_email_smtp_465(self, mock_smtp_ssl):
        # Set SMTP SSL variables
        os.environ["SMTP_SERVER"] = "smtp.mail.com"
        os.environ["SMTP_PORT"] = "465"
        os.environ["SMTP_USERNAME"] = "user"
        os.environ["SMTP_PASSWORD"] = "pass"

        server_instance = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = server_instance

        res = NotificationGateway.send_email("passenger@test.com", "Test Subject", "Test Body")
        self.assertTrue(res)
        server_instance.login.assert_called_with("user", "pass")
        server_instance.sendmail.assert_called_once()

    def test_notification_email_mock_fallback(self):
        # No SMTP variables -> should log mock only
        res = NotificationGateway.send_email("passenger@test.com", "Test Subject", "Test Body")
        self.assertTrue(res)

    @patch("urllib.request.urlopen")
    def test_notification_sms_twilio(self, mock_urlopen):
        os.environ["TWILIO_ACCOUNT_SID"] = "ACxxxx"
        os.environ["TWILIO_AUTH_TOKEN"] = "token123"
        os.environ["TWILIO_FROM_NUMBER"] = "+15005550006"

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "queued"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = NotificationGateway.send_sms("+1234567890", "Hello Test")
        self.assertTrue(res)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_notification_whatsapp_twilio(self, mock_urlopen):
        os.environ["TWILIO_ACCOUNT_SID"] = "ACxxxx"
        os.environ["TWILIO_AUTH_TOKEN"] = "token123"
        os.environ["TWILIO_FROM_WHATSAPP"] = "whatsapp:+15005550006"

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "queued"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = NotificationGateway.send_whatsapp("+1234567890", "Hello Whatsapp Test")
        self.assertTrue(res)
        mock_urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
