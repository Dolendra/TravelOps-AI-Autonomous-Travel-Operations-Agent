import unittest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.database.db import SessionLocal
from backend.database.models import UserModel, SessionModel

class TestAuthAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clear test accounts and sessions to isolate tests
        db = SessionLocal()
        try:
            db.query(UserModel).filter(UserModel.email.like("test_auth_api%")).delete()
            db.query(SessionModel).filter(SessionModel.session_id.like("test_auth_api%")).delete()
            db.commit()
        finally:
            db.close()

    def test_auth_and_session_isolation(self):
        # 1. Register User
        res = self.client.post("/api/auth/register", json={
            "email": "test_auth_api@travelops.com",
            "password": "SecuredPassword1!",
            "name": "Auth API User",
            "role": "passenger"
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json()["success"])

        # 2. Login User
        res = self.client.post("/api/auth/login", json={
            "email": "test_auth_api@travelops.com",
            "password": "SecuredPassword1!"
        })
        self.assertEqual(res.status_code, 200)
        tokens = res.json()
        self.assertIn("access_token", tokens)
        
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 3. Create Session with active User authorization
        res = self.client.post("/api/sessions", json={"session_id": "test_auth_api_sess"}, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "created")

        # 4. Get Session details with auth headers
        res = self.client.get("/api/sessions/test_auth_api_sess", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["session_id"], "test_auth_api_sess")

        # 5. Get Session details without auth headers (expected 401 Unauthorized)
        res = self.client.get("/api/sessions/test_auth_api_sess")
        self.assertEqual(res.status_code, 401)

        # 6. Session Ownership Isolation (User B trying to access User A's session)
        # Register User B
        res = self.client.post("/api/auth/register", json={
            "email": "test_auth_api_b@travelops.com",
            "password": "SecuredPassword2!",
            "name": "Auth API User B",
            "role": "passenger"
        })
        self.assertEqual(res.status_code, 201)

        # Login User B
        res = self.client.post("/api/auth/login", json={
            "email": "test_auth_api_b@travelops.com",
            "password": "SecuredPassword2!"
        })
        tokens_b = res.json()
        headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

        # Attempt to access User A's session using User B's token (expected 403 Forbidden)
        res = self.client.get("/api/sessions/test_auth_api_sess", headers=headers_b)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access denied", res.json()["detail"])

if __name__ == "__main__":
    unittest.main()
