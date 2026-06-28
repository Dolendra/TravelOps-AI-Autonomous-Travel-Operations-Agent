import unittest
from unittest.mock import patch, MagicMock
from travelops_sdk import (
    TravelOpsClient,
    TravelOpsError,
    AuthError,
    ValidationError,
    RateLimitError,
    APIError,
    SessionDetails,
    ObservabilityMetrics,
    EvaluationMetrics,
)


class TestTravelOpsClient(unittest.TestCase):
    def setUp(self):
        self.client = TravelOpsClient(base_url="http://localhost:8000")

    @patch("requests.request")
    def test_health_check(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_request.return_value = mock_response

        res = self.client.get_health()
        self.assertEqual(res["status"], "healthy")
        mock_request.assert_called_once_with(
            method="GET",
            url="http://localhost:8000/health",
            json=None,
            params=None,
            headers={},
            timeout=30,
        )

    @patch("requests.request")
    def test_register(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"success": True, "message": "Registered"}
        mock_request.return_value = mock_response

        res = self.client.register(
            email="test@test.com", password="pass", name="Test User", role="passenger"
        )
        self.assertTrue(res["success"])
        mock_request.assert_called_once_with(
            method="POST",
            url="http://localhost:8000/api/auth/register",
            json={
                "email": "test@test.com",
                "password": "pass",
                "name": "Test User",
                "role": "passenger",
            },
            params=None,
            headers={},
            timeout=30,
        )

    @patch("requests.request")
    def test_login(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "token123", "token_type": "bearer"}
        mock_request.return_value = mock_response

        tok = self.client.login(email="test@test.com", password="pass")
        self.assertEqual(tok, "token123")
        self.assertEqual(self.client.token, "token123")

    def test_unauthenticated_error(self):
        with self.assertRaises(AuthError):
            self.client.create_session()

    @patch("requests.request")
    def test_create_session(self, mock_request):
        self.client.set_token("token123")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"session_id": "sess_1", "status": "created"}
        mock_request.return_value = mock_response

        res = self.client.create_session(session_id="sess_1")
        self.assertEqual(res["session_id"], "sess_1")
        mock_request.assert_called_once_with(
            method="POST",
            url="http://localhost:8000/api/sessions",
            json={"session_id": "sess_1"},
            params=None,
            headers={"Authorization": "Bearer token123"},
            timeout=30,
        )

    @patch("requests.request")
    def test_get_session_details(self, mock_request):
        self.client.set_token("token123")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "sess_1",
            "created_at": "2026-06-28T00:00:00Z",
            "workflow_state": "BOOKED",
            "tasks": [
                {
                    "task_id": "t1",
                    "name": "hold_seat",
                    "status": "COMPLETED",
                    "dependencies": [],
                    "input_data": {},
                    "output_data": {},
                }
            ],
            "conversation": [
                {
                    "sender": "User",
                    "message": "Hi",
                    "timestamp": "2026-06-28T00:00:01Z",
                    "payload": None,
                }
            ],
        }
        mock_request.return_value = mock_response

        details = self.client.get_session_details("sess_1")
        self.assertIsInstance(details, SessionDetails)
        self.assertEqual(details.session_id, "sess_1")
        self.assertEqual(details.workflow_state, "BOOKED")
        self.assertEqual(len(details.tasks), 1)
        self.assertEqual(details.tasks[0].task_id, "t1")

    @patch("requests.request")
    def test_exception_mappings(self, mock_request):
        self.client.set_token("token123")

        # 400 Validation Error
        mock_resp_400 = MagicMock()
        mock_resp_400.status_code = 400
        mock_resp_400.json.return_value = {"detail": "Bad Request"}
        mock_request.return_value = mock_resp_400
        with self.assertRaises(ValidationError):
            self.client.create_session()

        # 401 Auth Error
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.json.return_value = {"detail": "Invalid credentials"}
        mock_request.return_value = mock_resp_401
        with self.assertRaises(AuthError):
            self.client.create_session()

        # 429 Rate Limit Error
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.json.return_value = {"detail": "Limit exceeded"}
        mock_request.return_value = mock_resp_429
        with self.assertRaises(RateLimitError):
            self.client.create_session()

        # 500 API Error
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.json.return_value = {"detail": "Internal crash"}
        mock_request.return_value = mock_resp_500
        with self.assertRaises(APIError):
            self.client.create_session()
