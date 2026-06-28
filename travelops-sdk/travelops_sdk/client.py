from typing import Any, Dict, List, Optional

import requests

from .exceptions import (
    APIError,
    AuthError,
    RateLimitError,
    TravelOpsError,
    ValidationError,
)
from .models import (
    EvaluationMetrics,
    ObservabilityMetrics,
    SessionDetails,
)


class TravelOpsClient:
    """Python Client SDK for interacting with the TravelOps AI platform."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        enforce_auth: bool = True,
    ) -> Any:
        """Helper to send HTTP requests and map status code responses to SDK exceptions."""
        url = f"{self.base_url}{path}"
        headers = {}

        if enforce_auth:
            if not self.token:
                raise AuthError("Client is not authenticated. Please run client.login() or client.set_token() first.")
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise TravelOpsError(f"HTTP request failed: {str(e)}")

        if response.status_code in (200, 201):
            try:
                return response.json()
            except ValueError:
                return response.text

        # Error handling
        status = response.status_code
        try:
            body = response.json()
            detail = body.get("detail", response.text)
        except ValueError:
            body = None
            detail = response.text

        msg = f"API Error [{status}]: {detail}"

        if status in (401, 403):
            raise AuthError(msg, status_code=status, response_body=response.text)
        elif status == 400:
            raise ValidationError(msg, status_code=status, response_body=response.text)
        elif status == 429:
            raise RateLimitError(msg, status_code=status, response_body=response.text)
        elif status >= 500:
            raise APIError(msg, status_code=status, response_body=response.text)
        else:
            raise TravelOpsError(msg, status_code=status, response_body=response.text)

    def get_health(self) -> Dict[str, Any]:
        """Check server health status."""
        return self._request("GET", "/health", enforce_auth=False)

    def register(self, email: str, password: str, name: str, role: str = "passenger") -> Dict[str, Any]:
        """Register a new user account."""
        payload = {"email": email, "password": password, "name": name, "role": role}
        return self._request("POST", "/api/auth/register", json=payload, enforce_auth=False)

    def login(self, email: str, password: str) -> str:
        """Authenticate user and store JWT token."""
        payload = {"email": email, "password": password}
        res = self._request("POST", "/api/auth/login", json=payload, enforce_auth=False)
        self.token = res["access_token"]
        return self.token

    def set_token(self, token: str):
        """Set JWT authorization token manually."""
        self.token = token

    def create_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new agent operations session."""
        payload = {}
        if session_id:
            payload["session_id"] = session_id
        return self._request("POST", "/api/sessions", json=payload)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions scoped to the authenticated user."""
        return self._request("GET", "/api/sessions")

    def get_session_details(self, session_id: str) -> SessionDetails:
        """Fetch details of a specific session and serialize them into SessionDetails."""
        res = self._request("GET", f"/api/sessions/{session_id}")
        return SessionDetails.model_validate(res)

    def get_session_studio_details(self, session_id: str) -> Dict[str, Any]:
        """Fetch developer studio details (event timeline, costs, provider health)."""
        return self._request("GET", f"/api/sessions/{session_id}/studio-details")

    def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a prompt/message query to the agent runtime."""
        payload = {"message": message}
        return self._request("POST", f"/api/sessions/{session_id}/message", json=payload)

    def run_session_workflow(self, session_id: str) -> Dict[str, Any]:
        """Trigger background workflow graph execution."""
        return self._request("POST", f"/api/sessions/{session_id}/run")

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Publish disruptive alerts/events to the async EventBus."""
        req_payload = {"event_type": event_type, "payload": payload}
        return self._request("POST", "/api/events/publish", json=req_payload)

    def approve_task(self, session_id: str, task_id: str) -> Dict[str, Any]:
        """Bypass manual operator approval blocks for a workflow task."""
        payload = {"task_id": task_id}
        return self._request("POST", f"/api/sessions/{session_id}/approve", json=payload)

    def execute_task(self, session_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Directly invoke a registered tool operation."""
        payload = {"tool_name": tool_name, "arguments": arguments}
        return self._request("POST", f"/api/sessions/{session_id}/execute-task", json=payload)

    def get_observability_metrics(self) -> ObservabilityMetrics:
        """Fetch global LLM cost, latency, and tools telemetry statistics."""
        res = self._request("GET", "/api/observability/metrics")
        return ObservabilityMetrics.model_validate(res)

    def get_evaluation_metrics(self) -> EvaluationMetrics:
        """Fetch live system evaluation performance accuracies."""
        res = self._request("GET", "/api/evaluation/metrics")
        return EvaluationMetrics.model_validate(res)
